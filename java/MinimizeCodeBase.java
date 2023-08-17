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
import java.util.LinkedHashSet;
import java.util.List;
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
        loadSourcepaths();
        loadFiles();
        loadDependencies();
        System.out.println();

        if (Files.exists(sourceFolder.resolve("pom.xml"))) {
            // mvn(sourceFolder, "--version");
            mvn(sourceFolder, "-q", "dependency:copy-dependencies");
            System.out.println();
        }

        copyPaths(sourceFolder, destinationFolder, files, true, null);
        System.out.println();

        final List<Path> jarsToCopy = new ArrayList<>();
        final List<Path> jarsNotCopiedDueToNameCollision = new ArrayList<>();
        final Set<Path> jarNames = new LinkedHashSet<>();
        final List<String> nonJarDependencies = new ArrayList<>();
        for (final String s : dependencies) {
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
            Files.createDirectories(jars);
            copyPaths(sourceFolder, jars, jarsToCopy, false, "jar");
        }

        Files.createDirectories(classOutput);
        System.out.println();

        final Iterable<? extends File> sourcepathsAsFiles = asFileIterable(sourcepaths);
        final Iterable<? extends File> filesAsFiles = asFileIterable(
                files.stream().filter(MinimizeCodeBase::isJavaSource));
        final Iterable<? extends File> jarsAsFiles = asFileIterable(jarNames.stream().map(jars::resolve));

        final DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<JavaFileObject>();
        final JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        final StandardJavaFileManager fileManager = compiler.getStandardFileManager(diagnostics, null, UTF_8);
        fileManager.setLocation(StandardLocation.CLASS_OUTPUT,
                Collections.singletonList(classOutput.toFile()));
        fileManager.setLocation(StandardLocation.SOURCE_PATH, sourcepathsAsFiles);
        if (!jarNames.isEmpty()) {
            fileManager.setLocation(StandardLocation.CLASS_PATH, jarsAsFiles);
        }

        final Iterable<? extends JavaFileObject> javaFiles = fileManager.getJavaFileObjectsFromFiles(filesAsFiles);
        final CompilationTask task = compiler.getTask(null, fileManager, diagnostics,
                null, null, javaFiles);
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
                final JavaFileObject source = diagnostic.getSource();
                if (null != previousSource && !previousSource.equals(source)) {
                    break;
                }
                final String code = diagnostic.getCode();
                boolean handled = false;
                if ("compiler.err.cant.resolve.location".equals(code)) {
                    final String message = diagnostic.getMessage(null);
                    final Matcher match = ERR_CANT_RESOLVE_LOCATION_MATCH_TYPE_SYMBOL_PACKAGE.matcher(message);
                    if (match.matches()) {
                        final String missing_symbol_type = match.group(1);
                        final String missing_symbol_name = match.group(2);
                        final String package_name = match.group(3);
                        if ("class".equals(missing_symbol_type)) {
                            System.out.println(".../" + package_name.replaceAll("\\.", "/") + "/" + missing_symbol_name
                                    + JavaFileObject.Kind.SOURCE.extension);
                            handled = true;
                            errorCount--;
                        } else {
                            System.out.println("----------");
                            show("code", code);
                            show("type", missing_symbol_type);
                            show("symbol", missing_symbol_name);
                            show("package", package_name);
                            System.out.println(diagnostic);
                            handled = true;
                        }
                    }
                }
                if (!handled) {
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
        addPathsFromListingToList(sourcepathsListing, sourcepaths);
    }

    protected void loadFiles() throws IOException {
        addPathsFromListingToList(filesListing, files);
    }

    protected void loadDependencies() throws IOException {
        if (Files.exists(dependenciesListing)) {
            addStringsFromListingToList(dependenciesListing, dependencies);
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

        this.sourcepathsListing = resolveRequiredListing("sourcepaths");
        this.filesListing = resolveRequiredListing("files");
        this.dependenciesListing = resolveOptionalListing("dependencies");
        this.classOutput = resolveOutputFolder("classes", "class output");
        this.jars = resolveOutputFolder("jars");

        this.sourcepaths = new ArrayList<>();
        this.files = new ArrayList<>();
        this.dependencies = new ArrayList<>();
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
    protected List<String> dependencies;

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
        return resolveAndCheckListing(basename, true);
    }

    protected Path resolveOptionalListing(final String basename) throws IOException {
        return resolveAndCheckListing(basename, false);
    }

    protected Path resolveOutputFolder(final String name, final String description) {
        final Path p = destinationFolder.resolve(name);
        return p;
    }

    protected Path resolveOutputFolder(final String name) {
        return resolveOutputFolder(name, name);
    }

    protected Path resolveAndCheckListing(final String basename, final String description, final boolean required)
            throws IOException {
        final Path p = destinationFolder.resolve(basename + ".lst");
        if (required) {
            checkRequiredFile(p, description);
        } else {
            checkRegularFile(p, description);
        }
        return p;

    }

    protected Path resolveAndCheckListing(final String basename, final boolean required) throws IOException {
        return resolveAndCheckListing(basename, basename + " listing", required);
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
     * @param sourcePaths                relative to sourceFolder
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
            final Collection<? extends Path> sourcePaths, final boolean preserveDestinationParents,
            final String descriptionSuffix, final CopyOption... copyOptions) throws IOException {
        final List<Path> copied = new ArrayList<>(sourcePaths.size());

        String srcDesc = "source";
        String dstDesc = "destination";
        if (!(null == descriptionSuffix || "".equals(descriptionSuffix))) {
            srcDesc += " " + descriptionSuffix;
            dstDesc += " " + descriptionSuffix;
        }
        final boolean replaceExisting = Arrays.stream(copyOptions)
                .anyMatch(o -> StandardCopyOption.REPLACE_EXISTING == o);

        System.out.println("ecp  path");
        for (final Path src : sourcePaths) {
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
    public static final Pattern ERR_CANT_RESOLVE_LOCATION_MATCH_TYPE_SYMBOL_PACKAGE = Pattern.compile(
            "cannot find symbol\\s+symbol:\\s+(class)\\s+("
                    + JAVA_IDENTIFIER_REGEX
                    + ")\\s+location:\\s+package\\s+("
                    + JAVA_IDENTIFIER_REGEX
                    + "(\\."
                    + JAVA_IDENTIFIER_REGEX
                    + ")*)",
            Pattern.MULTILINE);

    public static String escape(final String s) {
        final StringBuilder b = new StringBuilder();
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
        return b.toString();
    }
}
