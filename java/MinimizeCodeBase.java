import static java.nio.charset.StandardCharsets.UTF_8;

import java.io.File;
import java.io.IOException;
import java.io.PrintStream;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
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
        System.out.println("src exists? dst exists? path");
        for (final Path p : files) {
            final Path src = sourceFolder.resolve(p);
            checkRequiredFile(src, "source");
            final Path dst = destinationFolder.resolve(p);
            System.out.format("%-11b %-11b %s%n", Files.exists(src), Files.exists(dst),
                    p);
            if (!Files.exists(dst)) {
                Files.createDirectories(dst.getParent());
                Files.copy(src, dst);
                System.out.format("copied: %s%n", p);
            }
        }
        Files.createDirectories(classOutput);
        System.out.println();
        final Iterable<? extends File> sourcepathsAsFiles = asFileIterable(sourcepaths);
        final Iterable<? extends File> filesAsFiles = asFileIterable(
                files.stream().filter(MinimizeCodeBase::isJavaSource));

        if (Files.exists(sourceFolder.resolve("pom.xml"))) {
            final ProcessBuilder pb = new ProcessBuilder();
            pb.inheritIO();
            pb.directory(sourceFolder.toFile());
            pb.command("mvn", "dependency:copy-dependencies");
            final Process proc = pb.start();
            try {
                proc.waitFor();
            } catch (final InterruptedException e) {
                // TODO Auto-generated catch block
                e.printStackTrace();
            }
        }

        final DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<JavaFileObject>();
        final JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        final StandardJavaFileManager fileManager = compiler.getStandardFileManager(diagnostics, null, UTF_8);
        fileManager.setLocation(StandardLocation.CLASS_OUTPUT,
                Collections.singletonList(classOutput.toFile()));
        fileManager.setLocation(StandardLocation.SOURCE_PATH, sourcepathsAsFiles);
        final Iterable<? extends JavaFileObject> javaFiles = fileManager.getJavaFileObjectsFromFiles(filesAsFiles);
        final CompilationTask task = compiler.getTask(null, fileManager, diagnostics,
                null, null, javaFiles);
        if (!task.call()) {
            System.out.println("compilation failed");
        }

        for (final Diagnostic<? extends JavaFileObject> diagnostic : diagnostics.getDiagnostics()) {
            final Diagnostic.Kind kind = diagnostic.getKind();
            final String code = diagnostic.getCode();
            final long columnNumber = diagnostic.getColumnNumber();
            final long endPosition = diagnostic.getEndPosition();
            final long lineNumber = diagnostic.getLineNumber();
            final String message = diagnostic.getMessage(null);
            final long position = diagnostic.getPosition();
            final JavaFileObject source = diagnostic.getSource();
            final long startPosition = diagnostic.getStartPosition();

            if (Diagnostic.Kind.ERROR == kind) {
                if ("compiler.err.doesnt.exist".equals(code)) {
                    System.out.println(message);
                } else {
                    show(" ", "code", code);
                    show(" ", "columnNumber", columnNumber);
                    show(" ", "endPosition", endPosition);
                    show(" ", "kind", kind);
                    show(" ", "lineNumber", lineNumber);
                    show(" ", "message", message);
                    show(" ", "position", position);
                    show(" ", "source", source);
                    show(" ", "startPosition", startPosition);
                    break;
                }
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
        return Files.lines(p, UTF_8).filter(MinimizeCodeBase::isNotCommentLine);
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
}
