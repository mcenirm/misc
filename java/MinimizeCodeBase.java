import static java.nio.charset.StandardCharsets.UTF_8;

import java.io.File;
import java.io.IOException;
import java.io.PrintStream;
import java.lang.reflect.Method;
import java.nio.file.CopyOption;
import java.nio.file.Files;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaCompiler.CompilationTask;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.StandardLocation;
import javax.tools.ToolProvider;

public class MinimizeCodeBase {
    private final static String[] USAGE = {
            "Usage: %s source [destination]",
            "Where:",
            "  source         folder with full code base",
            "  destination    folder that will hold minimal code base [\".\"]",
    };

    public static void main(final String[] args) throws IOException {
        fromCommandLine(args).run();
    }

    public void run() throws IOException {
        this.loadSourcepaths();
        this.loadFiles();
        this.loadDependencies();
        System.out.println();

        if (Files.exists(this.sourceFolder.resolve("pom.xml"))) {
            // mvn(sourceFolder, "--version");
            mvn(this.sourceFolder, "-q", "dependency:copy-dependencies");
            System.out.println();
        }

        copyPaths(this.sourceFolder, this.destinationFolder, this.files, true, null);
        System.out.println();

        final List<Path> jarsToCopy = new ArrayList<>();
        final List<Path> jarsNotCopiedDueToNameCollision = new ArrayList<>();
        final Set<Path> jarNames = new LinkedHashSet<>();
        final List<String> nonJarDependencies = new ArrayList<>();
        for (final String s : this.dependencies) {
            try {
                final Path maybeJar = Paths.get(s);
                final Path name = maybeJar.getFileName();
                if (name.toString().endsWith(".jar")) {
                    final Path definitelyJar = maybeJar;
                    if (jarNames.contains(name)) {
                        jarsNotCopiedDueToNameCollision.add(definitelyJar);
                    } else {
                        jarsToCopy.add(definitelyJar);
                        jarNames.add(name);
                    }
                } else {
                    nonJarDependencies.add(s);
                }
            } catch (final InvalidPathException e) {
                nonJarDependencies.add(s);
            }
        }
        if (!jarsToCopy.isEmpty()) {
            Files.createDirectories(this.jars);
            copyPaths(this.sourceFolder, this.jars, jarsToCopy, false, "jar");
        }

        Files.createDirectories(this.classOutput);
        System.out.println();

        final Iterable<? extends File> sourcepathsAsFiles = asFileIterable(this.sourcepaths);
        final Iterable<? extends File> filesAsFiles = asFileIterable(this.javaFiles);
        final Iterable<? extends File> jarsAsFiles = asFileIterable(jarNames.stream().map(this.jars::resolve));

        final DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<JavaFileObject>();
        final JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        final StandardJavaFileManager fileManager = compiler.getStandardFileManager(diagnostics, null, UTF_8);
        fileManager.setLocation(StandardLocation.CLASS_OUTPUT,
                Collections.singletonList(this.classOutput.toFile()));
        fileManager.setLocation(StandardLocation.SOURCE_PATH, sourcepathsAsFiles);
        if (!jarNames.isEmpty()) {
            fileManager.setLocation(StandardLocation.CLASS_PATH, jarsAsFiles);
        }

        final Iterable<? extends JavaFileObject> javaFileObjects = fileManager
                .getJavaFileObjectsFromFiles(filesAsFiles);
        final CompilationTask task = compiler.getTask(null, fileManager, diagnostics, null, null, javaFileObjects);
        if (!task.call()) {
            System.out.println("compilation failed");
            System.out.println();
        }

        int errorCount = 0;
        JavaFileObject previousSource = null;
        for (final Diagnostic<? extends JavaFileObject> diagnostic : diagnostics.getDiagnostics()) {
            final Diagnostic.Kind kind = diagnostic.getKind();
            if (Diagnostic.Kind.ERROR == kind) {
                errorCount++;
                String guessJavaFile = null;
                String guessPackage = null;
                final JavaFileObject source = diagnostic.getSource();
                if (null != previousSource && !previousSource.equals(source)) {
                    break;
                }
                final String code = diagnostic.getCode();
                boolean handled = false;
                final String message = diagnostic.getMessage(null);
                if ("compiler.err.cant.resolve.location".equals(code)) {
                    final Matcher match = ERR_CANT_RESOLVE_LOCATION_MATCH_TYPE_SYMBOL_PACKAGE.matcher(message);
                    if (match.matches()) {
                        final String type = match.group(GROUP_KEYWORD);
                        final String symbol = match.group(GROUP_SYMBOL);
                        final String package_ = match.group(GROUP_PACKAGE);
                        if ("class".equals(type)) {
                            guessJavaFile = qualifiedNameToJavaFile(package_, symbol);
                            guessPackage = package_;
                        } else {
                            System.out.println("----------");
                            show("code", code);
                            show("type", type);
                            show("symbol", symbol);
                            show("package", package_);
                            System.out.println(diagnostic);
                            handled = true;
                        }
                    }
                } else if ("compiler.err.doesnt.exist".equals(code)) {
                    final String diagnosticString = diagnostic.toString();
                    final Matcher match = ERR_DOESNT_EXIST_MATCH_IMPORT.matcher(diagnosticString);
                    if (match.find()) {
                        guessPackage = match.group(GROUP_PACKAGE);
                        guessJavaFile = qualifiedNameToJavaFile(match.group(GROUP_TYPENAME));
                    } else {
                        System.out.println("----------");
                        show("source", source.getName());
                        System.out.println("-----");
                        System.out.println(diagnostic);
                        System.out.println("-----");
                        System.out.println(escape(diagnosticString));
                        System.out.println("-----");
                        handled = true;
                    }
                }
                if (null != guessJavaFile) {
                    final Path guessAsPath = Paths.get(guessJavaFile);
                    if (null == guessPackage) {
                        guessPackage = this.getPackageForJavaFile(guessAsPath);
                    }
                    final Set<Path> guessSourcepaths = this.getSourcepathsForPackage(guessPackage);
                    String guessSourcepath = null;
                    if (null == guessSourcepaths || guessSourcepaths.isEmpty()) {
                        guessSourcepath = "...";
                    } else {
                        guessSourcepath = guessSourcepaths.iterator().next().toString().replace(File.separatorChar,
                                '/');
                    }
                    System.out.println(guessSourcepath + "/" + guessJavaFile);
                    errorCount--;
                } else if (!handled) {
                    System.out.println("----------");
                    show("code", code);
                    System.out.println(diagnostic);
                    System.out.println();
                }
                if (errorCount >= 5) {
                    break;
                }
                previousSource = source;
            }
        }

        fileManager.close();
    }

    protected void loadSourcepaths() throws IOException {
        addPathsFromListingToList(this.sourcepathsListing, this.sourcepaths);
    }

    protected void loadFiles() throws IOException {
        addPathsFromListingToList(this.filesListing, this.files);
        this.files.stream().filter(MinimizeCodeBase::isJavaSource).forEachOrdered(this.javaFiles::add);
        for (final Path javaFile : this.javaFiles) {
            final List<Path> parentSourcepaths = this.sourcepaths.stream().filter(sp -> javaFile.startsWith(sp))
                    .collect(Collectors.toList());
            if (parentSourcepaths.size() < 1) {
                throw new IllegalArgumentException(String.format("no sourcepath for java file: %s", javaFile));
            } else if (parentSourcepaths.size() > 1) {
                System.out.println("Multiple matching sourcepaths for java file");
                show("  ", "java file", javaFile);
                show("  ", "sourcepaths", parentSourcepaths.size());
                for (final Path p : parentSourcepaths) {
                    show("    ", "", p);
                }
                System.out.println();
            } else {
                final Path sp = parentSourcepaths.get(0);
                this.sourcepathForJavaFile.put(javaFile, sp);
                final Path relativePath = sp.relativize(javaFile);
                final String package_ = foldersToQualifiedName(relativePath.getParent());
                this.packageForJavaFile.put(javaFile, package_);
                if (!this.sourcepathsForPackage.containsKey(package_)) {
                    this.sourcepathsForPackage.put(package_, new LinkedHashSet<>());
                }
                this.sourcepathsForPackage.get(package_).add(sp);
            }
        }
    }

    protected void loadDependencies() throws IOException {
        if (Files.exists(this.dependenciesListing)) {
            addStringsFromListingToList(this.dependenciesListing, this.dependencies);
        }
    }

    public MinimizeCodeBase(final Path sourceFolder, final Path destinationFolder) throws IOException {
        if (!Files.isDirectory(sourceFolder)) {
            throw new IllegalArgumentException(String.format("source is not a folder: %s", sourceFolder));
        }
        if (!Files.isDirectory(destinationFolder)) {
            throw new IllegalArgumentException(String.format("destination is not a folder: %s", destinationFolder));
        }
        if (Files.isSameFile(sourceFolder, destinationFolder)) {
            throw new IllegalArgumentException(String.format("source and destination are the same: %s", sourceFolder));
        }

        this.sourceFolder = sourceFolder;
        this.destinationFolder = destinationFolder;

        this.sourcepathsListing = this.resolveRequiredListing("sourcepaths");
        this.filesListing = this.resolveRequiredListing("files");
        this.dependenciesListing = this.resolveOptionalListing("dependencies");
        this.classOutput = this.resolveOutputFolder("classes", "class output");
        this.jars = this.resolveOutputFolder("jars");

        this.sourcepaths = new ArrayList<>();
        this.files = new ArrayList<>();
        this.javaFiles = new ArrayList<>();
        this.dependencies = new ArrayList<>();

        this.sourcepathForJavaFile = new HashMap<>();
        this.packageForJavaFile = new HashMap<>();
        this.sourcepathsForPackage = new HashMap<>();
    }

    protected Path sourceFolder;
    protected Path destinationFolder;
    protected Path sourcepathsListing;
    protected Path filesListing;
    protected Path dependenciesListing;
    protected Path classOutput;
    protected Path jars;
    protected List<Path> sourcepaths;
    protected List<Path> files;
    protected List<Path> javaFiles;
    protected List<String> dependencies;
    protected Map<Path, Path> sourcepathForJavaFile;
    protected Map<Path, String> packageForJavaFile;
    protected Map<String, Set<Path>> sourcepathsForPackage;

    public static MinimizeCodeBase fromCommandLine(final String[] args) throws IOException {
        int i = 0;
        while (i < args.length) {
            if ("--".equals(args[i])) {
                i++;
                break;
            } else if (args[i].startsWith("-")) {
                usage(0);
            } else {
                break;
            }
        }
        Path source = null;
        Path destination = Paths.get("");
        if (i < args.length) {
            source = Paths.get(args[i]);
            i++;
            if (i < args.length) {
                destination = Paths.get(args[i]);
                i++;
            }
        }
        if (i < args.length || null == source) {
            usage(1);
        }

        try {
            return new MinimizeCodeBase(source, destination);
        } catch (final IllegalArgumentException e) {
            System.err.println(e.getMessage());
            System.exit(1);
        }
        return null;
    }

    protected Path resolveRequiredListing(final String basename) throws IOException {
        return this.resolveAndCheckListing(basename, true);
    }

    protected Path resolveOptionalListing(final String basename) throws IOException {
        return this.resolveAndCheckListing(basename, false);
    }

    protected Path resolveOutputFolder(final String name, final String description) {
        final Path p = this.destinationFolder.resolve(name);
        return p;
    }

    protected Path resolveOutputFolder(final String name) {
        return this.resolveOutputFolder(name, name);
    }

    protected Path resolveAndCheckListing(final String basename, final String description, final boolean required)
            throws IOException {
        final Path p = this.destinationFolder.resolve(basename + ".lst");
        if (required) {
            checkRequiredFile(p, description);
        } else {
            checkRegularFile(p, description);
        }
        return p;

    }

    protected Path resolveAndCheckListing(final String basename, final boolean required) throws IOException {
        return this.resolveAndCheckListing(basename, basename + " listing", required);
    }

    protected Path getSourcepathForJavaFile(final Path javaFile) {
        return this.sourcepathForJavaFile.get(javaFile);
    }

    protected Set<Path> getSourcepathsForPackage(final String p) {
        return this.sourcepathsForPackage.get(p);
    }

    protected String getPackageForJavaFile(final Path p) {
        return this.packageForJavaFile.get(p);
    }

    public static void checkRequiredFile(final Path p, final String description) throws IOException {
        if (!Files.exists(p)) {
            throw new IllegalArgumentException(String.format("Missing %s file: %s", description, p));
        }
        checkRegularFile(p, description);
    }

    public static void checkRegularFile(final Path p, final String description) throws IOException {
        final String guess = guessPathType(p);
        switch (guess) {
            case "missing":
            case "file":
                return;
            default:
                throw new IllegalArgumentException(
                        String.format("Wrong type (%s) for %s file: %s", guess, description, p));
        }
    }

    public static void checkOptionalFolder(final Path p, final String description) throws IOException {
        final String guess = guessPathType(p);
        switch (guess) {
            case "missing":
            case "folder":
                return;
            default:
                throw new IllegalArgumentException(
                        String.format("Wrong type (%s) for %s folder: %s", guess, description, p));
        }
    }

    public static String guessPathType(final Path p) throws IOException {
        if (!Files.exists(p)) {
            return "missing";
        }
        if (Files.isDirectory(p)) {
            return "folder";
        }
        if (Files.isRegularFile(p)) {
            return "file";
        }
        if ((Boolean) Files.getAttribute(p, "isOther")) {
            return "other";
        }
        return "unknown";
    }

    public static void usage() {
        final PrintStream err = System.err;
        for (final String line : USAGE) {
            err.format(line, MinimizeCodeBase.class.getName());
            err.println();
        }
    }

    public static void usage(final int exitStatus) {
        usage();
        System.exit(exitStatus);
    }

    public static Iterable<? extends File> asFileIterable(final Stream<? extends Path> paths) {
        return () -> paths.map(Path::toFile).iterator();
    }

    public static Iterable<? extends File> asFileIterable(final Collection<? extends Path> paths) {
        return asFileIterable(paths.stream());
    }

    public static boolean isJavaSource(final Path p) {
        return p.getFileName().toString().endsWith(JavaFileObject.Kind.SOURCE.extension);
    }

    public static void inspect(final Object o) {
        System.out.println("----------");
        final Class<? extends Object> c = o.getClass();
        show("class", o.getClass());
        final Method[] ms = c.getDeclaredMethods();
        final String p = " ";
        for (int i = 0; i < ms.length; i++) {
            final Method m = ms[i];
            if (Void.TYPE.equals(m.getReturnType())) {
                continue;
            }
            if (0 == m.getParameterCount()) {
                continue;
            }
            final String n = m.getName();
            show(p, n, "...");
            // if (n.startsWith("get")) {
            // if (Character.isUpperCase(n.charAt(3))) {
            // }
            // }
            // show(p, "name", n);
            // show(p, "return type", r.getCanonicalName());
        }
        System.out.println("----------");
    }

    public static void show(final String prefix, final String name, final Object value) {
        System.out.format("%s%-20s %s%n", prefix, name, value);
    }

    public static void show(final String name, final Object value) {
        show("", name, value);
    }

    public static Stream<? extends Path> streamListingWithPaths(final Path p) throws IOException {
        return streamListing(p).map(Paths::get);
    }

    public static Stream<? extends String> streamListing(final Path p) throws IOException {
        return Files.lines(p, UTF_8).filter(MinimizeCodeBase::isNotCommentLine).filter(s -> !"".equals(s.trim()));
    }

    public static boolean isCommentLine(final String s) {
        return s.startsWith("#");
    }

    public static boolean isNotCommentLine(final String s) {
        return !isCommentLine(s);
    }

    public static void addPathsFromListingToList(final Path listing, final List<Path> list) throws IOException {
        list.addAll(streamListingWithPaths(listing).collect(Collectors.toList()));
    }

    public static void addStringsFromListingToList(final Path listing, final List<String> list) throws IOException {
        list.addAll(streamListing(listing).collect(Collectors.toList()));
    }

    public static void mvn(final File directory, final String... args) {
        final ProcessBuilder pb = new ProcessBuilder();
        pb.inheritIO();
        pb.directory(directory);
        final List<String> cmd = new ArrayList<>();
        cmd.add("mvn");
        cmd.addAll(Arrays.asList(args));
        pb.command(cmd);
        try {
            final Process proc = pb.start();
            proc.waitFor();
        } catch (final InterruptedException | IOException e) {
            // TODO Auto-generated catch block
            e.printStackTrace();
        }
    }

    public static void mvn(final Path directory, final String... args) {
        mvn(directory.toFile(), args);
    }

    /**
     * @param sourceFolder
     * @param destinationFolder
     * @param sources                    relative to sourceFolder
     * @param preserveDestinationParents maintain intermedate folders between
     *                                   destinationFolder and copied file,
     *                                   otherwise place file directly in
     *                                   destinationFolder
     * @param descriptionSuffix
     * @param copyOptions                used by
     *                                   {@see java.nio.file.Files#copy(Path, Path,
     *                                   CopyOption...)}
     * @return destination paths that were actually copied
     * @throws IOException
     */
    public static Iterable<? extends Path> copyPaths(final Path sourceFolder, final Path destinationFolder,
            final Collection<? extends Path> sources, final boolean preserveDestinationParents,
            final String descriptionSuffix, final CopyOption... copyOptions) throws IOException {
        final List<Path> copied = new ArrayList<>(sources.size());

        String srcDesc = "source";
        String dstDesc = "destination";
        if (!(null == descriptionSuffix || "".equals(descriptionSuffix))) {
            srcDesc += " " + descriptionSuffix;
            dstDesc += " " + descriptionSuffix;
        }
        final boolean replaceExisting = Arrays.stream(copyOptions)
                .anyMatch(o -> StandardCopyOption.REPLACE_EXISTING == o);

        System.out.println("ecp  path");
        for (final Path src : sources) {
            final Path resolvedSrc = sourceFolder.resolve(src);
            checkRequiredFile(resolvedSrc, srcDesc);

            final Path dst = preserveDestinationParents ? src : src.getFileName();
            final Path resolvedDst = destinationFolder.resolve(dst);
            checkRegularFile(resolvedDst, dstDesc);
            final boolean dstAlreadyExists = Files.exists(resolvedDst);

            final boolean shouldCopy = replaceExisting || !dstAlreadyExists;
            final boolean shouldCreateParents = preserveDestinationParents && !dstAlreadyExists;

            System.out.format("%c%c%c  %s%n", dstAlreadyExists ? 'e' : '.', shouldCopy ? 'c' : '.',
                    shouldCreateParents ? 'p' : '.', src);
            if (!shouldCopy) {
                continue;
            }
            if (shouldCreateParents) {
                Files.createDirectories(resolvedDst.getParent());
            }
            Files.copy(resolvedSrc, resolvedDst, copyOptions);
            copied.add(dst);
        }
        return copied;
    }

    public static final String JAVA_IDENTIFIER_REGEX = "\\p{javaJavaIdentifierStart}\\p{javaJavaIdentifierPart}*";
    public static final String JAVA_PACKAGE_REGEX = JAVA_IDENTIFIER_REGEX
            + "(?:\\."
            + JAVA_IDENTIFIER_REGEX
            + ")*";;

    public static final String GROUP_KEYWORD = "keyword";
    public static final String GROUP_PACKAGE = "package";
    public static final String GROUP_SYMBOL = "symbol";
    public static final String GROUP_TYPENAME = "typename";

    public static final Pattern ERR_CANT_RESOLVE_LOCATION_MATCH_TYPE_SYMBOL_PACKAGE = Pattern.compile(
            "cannot find symbol\\s+symbol:\\s+(?<"
                    + GROUP_KEYWORD
                    + ">class)\\s+(?<"
                    + GROUP_SYMBOL
                    + ">"
                    + JAVA_IDENTIFIER_REGEX
                    + ")\\s+location:\\s+package\\s+(?<"
                    + GROUP_PACKAGE
                    + ">"
                    + JAVA_PACKAGE_REGEX
                    + ")",
            Pattern.MULTILINE);

    public static final Pattern ERR_DOESNT_EXIST_MATCH_IMPORT = Pattern.compile(
            "\\spackage\\s+(?<"
                    + GROUP_PACKAGE
                    + ">"
                    + JAVA_PACKAGE_REGEX
                    + ")\\s+does\\s+not\\s+exist\\s+import\\s+(?<"
                    + GROUP_TYPENAME
                    + ">\\k<"
                    + GROUP_PACKAGE
                    + ">\\."
                    + JAVA_IDENTIFIER_REGEX
                    + ")\\s*;\\s",
            Pattern.MULTILINE);

    public static String escape(final String s) {
        if (null == s) {
            return null;
        }
        final StringBuilder b = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            final char c = s.charAt(i);
            switch (c) {
                case '\b':
                    b.append("\\b");
                    break;
                case '\t':
                    b.append("\\t");
                    break;
                case '\n':
                    b.append("\\n");
                    break;
                case '\f':
                    b.append("\\f");
                    break;
                case '\r':
                    b.append("\\r");
                    break;
                case '\"':
                    b.append("\\\"");
                    break;
                case '\'':
                    b.append("\\\'");
                    break;
                case '\\':
                    b.append("\\\\");
                    break;
                default:
                    b.append(c);
                    break;
            }
        }
        b.append("\"");
        return b.toString();
    }

    public static String qualifedNameToFolders(final String name, final String... more) {
        if (null == name || Arrays.stream(more).anyMatch(s -> null == s)) {
            return null;
        }
        final StringBuilder b = new StringBuilder(name.replace('.', '/'));
        for (int i = 0; i < more.length; i++) {
            b.append('/');
            b.append(more[i].replace('.', '/'));
        }
        return b.toString();
    }

    public static String qualifiedNameToJavaFile(final String name, final String... more) {
        final String base = qualifedNameToFolders(name, more);
        if (null == base) {
            return null;
        }
        return base + JavaFileObject.Kind.SOURCE.extension;
    }

    public static String foldersToQualifiedName(final Path p) {
        if (null == p) {
            return null;
        }
        final Iterator<Path> it = p.iterator();
        final StringBuilder b = new StringBuilder(it.next().toString());
        while (it.hasNext()) {
            b.append('.');
            b.append(it.next().toString());
        }
        return b.toString();
    }
}
