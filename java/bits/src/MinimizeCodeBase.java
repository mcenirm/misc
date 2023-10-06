import static java.nio.charset.StandardCharsets.UTF_8;

import java.io.File;
import java.io.IOException;
import java.io.OutputStream;
import java.io.PrintStream;
import java.io.PrintWriter;
import java.io.Writer;
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
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;
import java.util.Optional;
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
            "Usage: %1$s original [destination]",
            "Where:",
            "  original       folder with full code base",
            "  destination    folder that will hold minimal code base [\".\"]",
            "                 subfolders:",
            "                  - classes/    compiled class files",
            "                  - jars/       jar file dependencies",
            "                  - sources/    java source files and resource files",
    };

    public static void main(final String[] args) throws IOException {
        fromCommandLine(args).run();
        showPatternTimes();
    }

    public void run() throws IOException {
        this.loadListings();
        this.rebuildCaches();
        // this.useMavenToCollectDependencies();
        this.copyFilesAndDependencies();
        this.compile();

        if (this.compilationResult.wasSuccessful) {
            return;
        }

        ///////////////////////////////////////

        // show error code counts and collect errors from just the first N java files
        // TODO keep going for all?
        final int javaFileLimit = 10;
        final Map<CopiedJavaFile, List<Diagnostic<? extends JavaFileObject>>> errorsByJavaFile = new LinkedHashMap<>();
        final PrintWriter errorsPrinter = new PrintWriter(this.destinationClassesFolder
                .resolve("errors.txt")
                .toFile());
        try {
            this.out.println("-- error code counts -- ");
            final Iterator<Entry<JavaFileObject, List<Diagnostic<? extends JavaFileObject>>>> entries = this.compilationResult.errorsBySource
                    .entrySet()
                    .iterator();
            int i = 0;
            while (i < javaFileLimit && entries.hasNext()) {
                i++;
                final Entry<JavaFileObject, List<Diagnostic<? extends JavaFileObject>>> entry = entries.next();
                final JavaFileObject source = entry.getKey();
                final CopiedJavaFile javaFile = this.javaFileHelper.lookup(source);
                final List<Diagnostic<? extends JavaFileObject>> errors = entry.getValue();
                errorsByJavaFile.put(javaFile, errors);
                this.out.println(javaFile.forListing());
                this.compilationResult.statisticsBySource.get(source).countsByCode
                        .entrySet()
                        .stream()
                        .sorted(Map.Entry.<ErrorCode, Integer>comparingByValue().reversed())
                        .forEach(e -> this.out.format(
                                "%4d  %s%n",
                                e.getValue(),
                                e.getKey()));
                for (final Diagnostic<? extends JavaFileObject> error : errors) {
                    errorsPrinter.println("----------------");
                    errorsPrinter.println(error.getCode());
                    errorsPrinter.println();
                    errorsPrinter.println(error.toString().replaceFirst(
                            ": error: ",
                            ":\nerror: "));
                    errorsPrinter.println();
                }
            }
            if (i > 1) {
                this.out.println("totals");
                this.compilationResult.statistics.countsByCode
                        .entrySet()
                        .stream()
                        .sorted(Map.Entry.<ErrorCode, Integer>comparingByValue().reversed())
                        .forEach(e -> this.out.format(
                                "%4d  %s%n",
                                e.getValue(),
                                e.getKey()));
            }
            this.out.println();
        } finally {
            errorsPrinter.close();
        }

        ///////////////////////////////////////

        // for each java file, look at errors and guess dependencies
        final Map<JavaName, Set<CopiedJavaFile>> missingImportsAndTheJavaFilesThatNeedThem = new LinkedHashMap<>();
        final Map<CopiedJavaFile, Set<JavaName>> javaFilesWithMissingSymbols = new LinkedHashMap<>();
        for (final Entry<CopiedJavaFile, List<Diagnostic<? extends JavaFileObject>>> entry : errorsByJavaFile
                .entrySet()) {
            final CopiedJavaFile javaFile = entry.getKey();
            final List<Diagnostic<? extends JavaFileObject>> errors = entry.getValue();

            final Map<JavaName, JavaName> importsBySymbolForCurrentJavaFile = new LinkedHashMap<>();
            for (final Diagnostic<? extends JavaFileObject> error : errors) {
                final List<DecodedDiagnostic> decodedDiagnostics = decodeDiagnostic(error);
                if (1 != decodedDiagnostics.size()) {
                    this.out.println("---- expected one decoded diagnostic ----");
                    this.out.show("decoded #", decodedDiagnostics.size());
                    this.out.println(error.toString().replaceAll("(?m)^", "> "));
                    for (final DecodedDiagnostic dd : decodedDiagnostics) {
                        this.out.println();
                        this.out.show("-- ", dd);
                    }
                    return;
                }
                final DecodedDiagnostic decoded = decodedDiagnostics.get(0);
                final ErrorCode code = ErrorCode.fromText(error.getCode());
                if (ErrorCode.DOESNT_EXIST == code
                        && ErrorCategory.PACKAGE_DOES_NOT_EXIST == decoded.category
                        && null != decoded.packageName
                        && null != decoded.symbol
                        && null != decoded.typename) {
                    /*
                     * > error: package <PACKAGE> does not exist
                     * > import <PACKAGE>.<SYMBOL>;
                     */
                    final JavaName importedType = decoded.typename;
                    final JavaName previousImportedType = importsBySymbolForCurrentJavaFile.put(
                            decoded.symbol,
                            importedType);
                    if (null != previousImportedType && !previousImportedType.equals(importedType)) {
                        this.out.show("collision", previousImportedType + " vs " + importedType);
                    }
                    missingImportsAndTheJavaFilesThatNeedThem
                            .computeIfAbsent(importedType, k -> new LinkedHashSet<>())
                            .add(javaFile);
                } else if (ErrorCode.DOESNT_EXIST == code
                        && ErrorCategory.PACKAGE_DOES_NOT_EXIST == decoded.category
                        && null != decoded.packageName
                        && null == decoded.symbol
                        && null == decoded.typename) {
                    /*
                     * > error: package <PACKAGE> does not exist
                     * 
                     * Without "import", this is probably a multi-level member access to a type in
                     * the same source package. (eg, "Foo.someStaticMember.someMember")
                     */
                    javaFilesWithMissingSymbols
                            .computeIfAbsent(javaFile, k -> new LinkedHashSet<>())
                            .add(decoded.packageName);
                } else if (ErrorCode.CANT_RESOLVE_LOCATION == code
                        && ErrorCategory.CANNOT_FIND_SYMBOL == decoded.category
                        && null != decoded.symbol) {
                    /*
                     * > error: cannot find symbol
                     * > ...
                     * > symbol: <class|variable> <SYMBOL>
                     * > ...
                     * 
                     * With "class", this is probably a reference to an import.
                     * 
                     * With "variable", this is probably a single-level member access to a type in
                     * the same source package. (eg, "Foo.someStaticMember")
                     */
                    if (importsBySymbolForCurrentJavaFile.containsKey(decoded.symbol)) {
                        // ignore, since fixing import would fix this reference to it
                    } else {
                        javaFilesWithMissingSymbols
                                .computeIfAbsent(javaFile, k -> new LinkedHashSet<>())
                                .add(decoded.symbol);
                    }
                } else {
                    this.out.show("code", code);
                    this.out.show("  ", decoded);
                    this.out.println(error.toString().replaceAll("(?m)^", "> "));
                    break;
                }
            }
        }

        ///////////////////////////////////////

        // list missing symbols and imports
        if (!javaFilesWithMissingSymbols.isEmpty()) {
            this.out.println("---- missing symbols by java file ----");
            for (final Entry<CopiedJavaFile, Set<JavaName>> entry : javaFilesWithMissingSymbols.entrySet()) {
                final CopiedJavaFile javaFile = entry.getKey();
                final Set<JavaName> symbols = entry.getValue();
                this.out.println(javaFile.forListing());
                if (!symbols.isEmpty()) {
                    for (final JavaName symbol : symbols) {
                        this.out.println("  " + symbol);
                    }
                }
            }
            this.out.println();
        }
        if (!missingImportsAndTheJavaFilesThatNeedThem.isEmpty()) {
            this.out.println("---- missing imports ----");
            for (final JavaName missingImport : missingImportsAndTheJavaFilesThatNeedThem.keySet()) {
                this.out.println(missingImport);
            }
            this.out.println();
        }

        ///////////////////////////////////////

        // collect easy candidates
        /*
         * Example 1
         * * when dest/sources/.../com/example/Foo.java uses simple symbol Bar
         * * and original...../.../com/example/Bar.java exists
         * * then suggest....: .../com/example/Bar.java
         */
        final Set<CopiedJavaFile> candidateJavaFiles = new LinkedHashSet<>();
        if (!javaFilesWithMissingSymbols.isEmpty()) {
            for (final Entry<CopiedJavaFile, Set<JavaName>> entry : javaFilesWithMissingSymbols.entrySet()) {
                final CopiedJavaFile javaFile = entry.getKey();
                final Set<JavaName> symbols = entry.getValue();
                if (!symbols.isEmpty()) {
                    final Path originalPackageFolder = javaFile.originalResolved.getParent();
                    final Path relativePackageFolder = javaFile.relative.getParent();
                    for (final JavaName symbol : symbols) {
                        if (symbol.isSimpleName) {
                            final String fileName = symbol.name + CopiedJavaFile.EXTENSION;
                            final Path originalCandidate = originalPackageFolder.resolve(fileName);
                            if (Files.exists(originalCandidate)) {
                                final Path relativeCandidate = relativePackageFolder.resolve(fileName);
                                candidateJavaFiles.add(this.javaFileHelper.lookup(relativeCandidate));
                            }
                        }
                    }
                }
            }
        }

        // TODO find candidate imports using jar files from originalFolder
        if (!missingImportsAndTheJavaFilesThatNeedThem.isEmpty()) {
            this.out.println("---- lalala ----");
            for (final Entry<JavaName, Set<CopiedJavaFile>> entry : missingImportsAndTheJavaFilesThatNeedThem
                    .entrySet()) {
                final JavaName missingImport = entry.getKey();
                final Set<CopiedJavaFile> javaFiles = entry.getValue();
                this.out.println();
                this.out.println(missingImport);
                for (final CopiedJavaFile javaFile : javaFiles) {
                    this.out.println("  " + javaFile.forListing());
                    if (javaFile.packageName.isPresent()) {
                        this.out.println("    " + javaFile.packageName.get().toString());
                    } else {
                        this.out.println("    <unguessed package>");
                    }
                }
                // Files.find(classesFolder, javaFileLimit, null, null);
            }
            this.out.println();
        }

        ///////////////////////////////////////

        if (!candidateJavaFiles.isEmpty()) {
            this.out.println("---- candidate java files ----");
            for (final CopiedJavaFile candidate : candidateJavaFiles) {
                this.out.println(candidate.forListing());
            }
            this.out.println();
        }

        ///////////////////////////////////////

        // int unmatchedErrorCount = 0;
        // JavaFileObject previousSource = null;
        // for (final Diagnostic<? extends JavaFileObject> diag :
        // this.compilationResult.errors) {
        // if (Diagnostic.Kind.ERROR == diag.getKind()) {
        // unmatchedErrorCount++;
        // final ErrorCode code = ErrorCode.fromText(diag.getCode());
        // final JavaFileObject source = diag.getSource();
        // if (null != previousSource && !previousSource.equals(source)) {
        // break;
        // }
        // if (!this.unresolvedPackagesForSymbolsBySource.containsKey(source)) {
        // this.unresolvedPackagesForSymbolsBySource.put(source, new LinkedHashMap<>());
        // }
        // final Map<String, Set<String>> unresolvedPackagesForSymbols =
        // this.unresolvedPackagesForSymbolsBySource
        // .get(source);
        // final Map<String, String> resolvedPackageForSymbol = new LinkedHashMap<>();

        // final DecodedDiagnostic dd = decodedDiagnostics.get(0);
        // boolean matched = true;
        // if (ErrorCode.DOESNT_EXIST == code
        // && null != dd.packageName
        // && null != dd.typename) {
        // this.unresolvedPackages.put(dd.packageName, dd);
        // if (null != dd.symbol) {
        // if (!resolvedPackageForSymbol.containsKey(dd.symbol)) {
        // if (!unresolvedPackagesForSymbols.containsKey(dd.symbol)) {
        // unresolvedPackagesForSymbols.put(dd.symbol, new LinkedHashSet<>());
        // }
        // unresolvedPackagesForSymbols.get(dd.symbol).add(dd.packageName);
        // }
        // }
        // } else if (ErrorCode.CANT_RESOLVE_LOCATION == code
        // && JAVA_KEYWORD_CLASS.equals(dd.keyword)
        // && null != dd.symbol
        // && unresolvedPackagesForSymbols.containsKey(dd.symbol)) {
        // final Set<String> packageSet = unresolvedPackagesForSymbols.get(dd.symbol);
        // if (packageSet.size() > 1) {

        // }
        // // this.unresolvedQualifiedNames
        // } else {
        // matched = false;
        // }
        // if (matched) {
        // this.codeScores.merge(code.text, 1, Integer::sum);
        // unmatchedErrorCount--;
        // } else {
        // this.out.println("----------");
        // this.out.show("code", code);
        // // this.out.show("source", source.getName());
        // this.out.show("message", StaticHelpers.escape(diag.getMessage(null)));
        // this.out.println("--");
        // this.out.println(diag);
        // // this.out.println("--");
        // this.out.println("----------");
        // this.out.show(dd);
        // this.out.println();
        // }

        // final Path guessJavaFile = null;
        // String guessPackage = null;
        // if (null != guessJavaFile) {
        // if (null == guessPackage) {
        // guessPackage = this.getPackageForJavaFile(guessJavaFile);
        // }
        // final Set<Path> guessSourcepaths =
        // this.getSourcepathsForPackage(guessPackage);
        // if (!guessSourcepaths.isEmpty()) {
        // for (final Path guessSourcePath : guessSourcepaths) {
        // this.suggestedJavaFiles.add(guessSourcePath.resolve(guessJavaFile));
        // }
        // } else {
        // boolean foundJavaFile = false;
        // for (final Path sp : this.sourcepaths) {
        // final Path withSourcepath = sp.resolve(guessJavaFile);
        // if (Files.exists(this.sourceFolder.resolve(withSourcepath))) {
        // this.suggestedJavaFiles.add(withSourcepath);
        // foundJavaFile = true;
        // }
        // }
        // if (!foundJavaFile) {
        // this.suggestedUnresolvedJavaFiles.add(guessJavaFile);
        // final String typename = dd.typename;
        // final Optional<Path> alreadyFoundJarWithType =
        // this.suggestedJars.stream().filter(j -> {
        // return jarContainsType(j, typename);
        // }).findFirst();
        // if (!alreadyFoundJarWithType.isPresent()) {
        // final Optional<Path> foundJarWithType = this.jarsToCopy.stream()
        // .map(Path::getParent)
        // .unordered()
        // .distinct()
        // .map(this.sourceFolder::resolve)
        // .flatMap(parent -> {
        // try {
        // return Files.find(parent, 1, (file, attr) -> isJar(file));
        // } catch (final IOException e) {
        // // TODO Auto-generated catch block
        // e.printStackTrace();
        // return Stream.empty();
        // }
        // })
        // .filter(j -> !this.jarNames.contains(j.getFileName()))
        // .filter(j -> {
        // return jarContainsType(j, typename);
        // })
        // .findFirst();
        // if (foundJarWithType.isPresent()) {
        // this.suggestedJars.add(foundJarWithType.get());
        // }
        // }
        // }
        // }
        // }
        // if (unmatchedErrorCount >= 1 /* 5 */) {
        // // only show the first N errors that could not be mitigated
        // // TODO show all errors
        // break;
        // }
        // previousSource = source;
        // }
        // }

        // if (!this.unresolvedPackages.isEmpty())

        // {
        // this.out.println("-- unresolved packages --");
        // for (

        // final String packageName : this.unresolvedPackages.keySet()) {
        // this.out.println(this.packageName);
        // }
        // this.out.println();
        // }

        // if (!this.unresolvedPackagesForSymbolsBySource.isEmpty()) {
        // this.out.println("-- unresolved packages for symbols --");
        // for (final Entry<String, Set<String>> entry :
        // this.unresolvedPackagesForSymbolsBySource.entrySet()) {
        // final String symbolName = entry.getKey();
        // final Set<String> packageSet = entry.getValue();
        // for (final String packageName : packageSet) {
        // this.out.println(symbolName + " - " + packageName);
        // }
        // }
        // this.out.println();
        // }

        // if (!this.suggestedSourcepaths.isEmpty()) {
        // this.out.println("-- suggested sourcepaths --");
        // for (final Path suggestedSourcepath : this.suggestedSourcepaths) {
        // this.out.println(preparePathForListing(this.suggestedSourcepath));
        // }
        // this.out.println();
        // }

        // if (!this.suggestedUnresolvedJavaFiles.isEmpty()) {
        // this.out.println("-- suggested unresolved java files --");
        // for (final Path unresolvedJavaFile : this.suggestedUnresolvedJavaFiles) {
        // this.out.println("TBD/" + preparePathForListing(this.unresolvedJavaFile));
        // }
        // this.out.println();
        // }

        // if (!this.suggestedJavaFiles.isEmpty()) {
        // this.out.println("-- suggested java files --");
        // for (final Path javaFile : this.suggestedJavaFiles) {
        // this.out.println(preparePathForListing(this.javaFile));
        // }
        // this.out.println();
        // }

        // if (!this.suggestedJars.isEmpty()) {
        // this.out.println("-- suggested jars --");
        // for (final Path jar : this.suggestedJars) {
        // this.out.println(preparePathForListing(this.sourceFolder.relativize(this.jar)));
        // }
        // this.out.println();
        // }
        // for (final CopiedJarFile jar :
        // this.jarFileHelper.mapByOriginalRelative.values()) {
        // this.out.show(" ", jar);
        // this.out.println();
        // }
    }

    protected void loadListings() throws IOException {
        this.loadFiles();
        this.loadSourcepaths();
        this.loadDependencies();
    }

    protected void rebuildCaches() throws IOException {
        this.identifyJavaFiles();
        this.identifyJarFiles();
    }

    protected void useMavenToCollectDependencies() {
        if (Files.exists(this.originalFolder.resolve("pom.xml"))) {
            // mvn(sourceFolder, "--version");
            StaticHelpers.mvn(this.originalFolder, "-q", "dependency:copy-dependencies");
            this.out.println();
        }
    }

    protected void copyFilesAndDependencies() throws IOException {
        Files.createDirectories(this.destinationSourcesFolder);
        this.copyFiles(
                this.originalFolder,
                this.destinationSourcesFolder,
                this.files,
                true,
                null);

        if (!this.jarsToCopy.isEmpty()) {
            Files.createDirectories(this.destinationJarsFolder);
            this.copyFiles(
                    this.originalFolder,
                    this.destinationJarsFolder,
                    this.jarsToCopy,
                    false,
                    "jar");
        }
    }

    protected void compile() throws IOException {
        this.compilationResult = StaticHelpers.compile(
                this.destinationClassesFolder.toFile(),
                StaticHelpers.asFileIterable(this.javaFiles.stream().map(f -> f.destinationResolved)),
                StaticHelpers.asFileIterable(this.sourcepaths.stream().map(this.destinationSourcesFolder::resolve)),
                StaticHelpers.asFileIterable(this.jarFiles.stream().map(f -> f.destinationResolved)));
    }

    protected void loadFiles() throws IOException {
        StaticHelpers.addPathsFromListingToList(this.filesListing, this.files);
    }

    protected void loadSourcepaths() throws IOException {
        if (Files.exists(this.sourcepathsListing)) {
            StaticHelpers.addPathsFromListingToList(this.sourcepathsListing, this.sourcepaths);
        }
    }

    protected void loadDependencies() throws IOException {
        if (Files.exists(this.dependenciesListing)) {
            StaticHelpers.addStringsFromListingToList(this.dependenciesListing, this.dependencies);
        }
    }

    protected void identifyJavaFiles() throws IOException {
        this.javaFileHelper.clear();
        for (final Path fileAsPath : this.files) {
            if (CopiedJavaFile.isJavaSource(fileAsPath)) {
                final CopiedJavaFile fileAsJavaFile = this.javaFileHelper.lookup(fileAsPath);
                this.javaFiles.add(fileAsJavaFile);
            }
        }
    }

    protected void identifyJarFiles() {
        this.jarFileHelper.clear();

        this.jarsToCopy.clear();
        this.jarsNotCopiedDueToNameCollision.clear();
        this.nonJarDependencies.clear();

        final Set<Path> jarNames = new LinkedHashSet<>();

        for (final String s : this.dependencies) {
            try {
                final Path originalRelative = Paths.get(s);
                try {
                    final CopiedJarFile jarFile = this.jarFileHelper.lookup(originalRelative);
                    if (jarNames.contains(jarFile.fileName)) {
                        this.jarsNotCopiedDueToNameCollision.add(originalRelative);
                    } else {
                        this.jarsToCopy.add(originalRelative);
                        this.jarFiles.add(jarFile);
                        jarNames.add(jarFile.fileName);
                    }
                } catch (final IllegalArgumentException e) {
                    this.nonJarDependencies.add(s);
                }
            } catch (final InvalidPathException e) {
                this.nonJarDependencies.add(s);
            }
        }
    }

    protected void checkJavaFiles() throws IOException {
        for (final CopiedJavaFile javaFile : this.javaFiles) {
            final List<Path> parentSourcepaths = this.sourcepaths
                    .stream()
                    .filter(sourcepath -> javaFile.relative.startsWith(sourcepath))
                    .collect(Collectors.toList());
            if (parentSourcepaths.size() < 1) {
                // final StringBuilder message = new StringBuilder()
                // .append("no sourcepath for java file: ")
                // .append(javaFile.toString());
                // final List<Path> guesses = guessSourcepathFromJavaFile(javaFile);
                // if (!guesses.isEmpty()) {
                // message.append(String.format("%n-- suggested sourcepaths --"));
                // for (final Path guess : guesses) {
                // message.append(String.format("%n%s", guess));
                // }
                // message.append(String.format("%n"));
                // }
                // throw new IllegalArgumentException(message.toString());
            } else if (parentSourcepaths.size() > 1) {
                this.out.println("Multiple matching sourcepaths for java file");
                this.out.show("  ", "java file", javaFile);
                this.out.show("  ", "sourcepaths", parentSourcepaths.size());
                for (final Path p : parentSourcepaths) {
                    this.out.show("    ", "", p);
                }
                this.out.println();
            } else {
                final Path sourcepath = parentSourcepaths.get(0);
                this.sourcepathForJavaFile.put(javaFile, sourcepath);
                final Path relativePath = sourcepath.relativize(javaFile.relative);
                final JavaName packageName = JavaName.fromFolders(relativePath.getParent());
                this.packageForJavaFile.put(javaFile, packageName);
                this.sourcepathsForPackage
                        .computeIfAbsent(packageName, k -> new LinkedHashSet<>())
                        .add(sourcepath);
            }
        }
    }

    public MinimizeCodeBase(
            final Path originalFolder,
            final Path destinationFolder)
            throws IOException {
        this(originalFolder, destinationFolder, System.out);
    }

    public MinimizeCodeBase(
            final Path originalFolder,
            final Path destinationFolder,
            final PrintStream out)
            throws IOException {
        this(originalFolder, destinationFolder, out, System.err);
    }

    public MinimizeCodeBase(
            final Path originalFolder,
            final Path destinationFolder,
            final PrintStream out,
            final PrintStream err)
            throws IOException {
        if (!Files.isDirectory(originalFolder)) {
            throw new IllegalArgumentException(String.format("original is not a folder: %s", originalFolder));
        }
        if (!Files.isDirectory(destinationFolder)) {
            throw new IllegalArgumentException(String.format("destination is not a folder: %s", destinationFolder));
        }
        if (Files.isSameFile(originalFolder, destinationFolder)) {
            throw new IllegalArgumentException(
                    String.format("original and destination are the same: %s", originalFolder));
        }

        // constructor arguments
        this.originalFolder = originalFolder;
        this.destinationFolder = destinationFolder;
        this.out = new ShowStream(null != out ? out : new NullOutputStream());
        this.err = null != err ? err : new PrintStream(new NullOutputStream());

        // destination items
        this.filesListing = this.resolveRequiredListing("files");
        this.sourcepathsListing = this.resolveOptionalListing("sourcepaths");
        this.dependenciesListing = this.resolveOptionalListing("dependencies");
        this.destinationSourcesFolder = this.resolveDestinationFolder("sources");
        this.destinationClassesFolder = this.resolveDestinationFolder("classes");
        this.destinationJarsFolder = this.resolveDestinationFolder("jars");

        // items loaded from listings
        this.sourcepaths = new ArrayList<>();
        this.files = new ArrayList<>();
        this.dependencies = new ArrayList<>();

        // calculated collections (cleared at start of run)
        this.javaFileHelper = new CopiedJavaFileHelper(
                this.originalFolder,
                this.destinationSourcesFolder);
        this.javaFiles = new ArrayList<>();
        this.jarFileHelper = new CopiedJarFileHelper(
                this.originalFolder,
                this.destinationJarsFolder);
        this.jarFiles = new ArrayList<>();
        this.jarsToCopy = new ArrayList<>();
        this.jarsNotCopiedDueToNameCollision = new ArrayList<>();
        this.nonJarDependencies = new ArrayList<>();
        this.sourcepathForJavaFile = new HashMap<>();
        this.packageForJavaFile = new HashMap<>();
        this.sourcepathsForPackage = new HashMap<>();

        // results and suggestions
        this.unresolvedQualifiedNames = new LinkedHashMap<>();
        this.unresolvedPackages = new LinkedHashMap<>();
        this.unresolvedPackagesForSymbolsBySource = new LinkedHashMap<>();
        this.suggestedSourcepaths = new LinkedHashSet<>();
        this.suggestedUnresolvedJavaFiles = new LinkedHashSet<>();
        this.suggestedJavaFiles = new LinkedHashSet<>();
        this.suggestedJars = new LinkedHashSet<>();
        this.codeScores = new HashMap<>();
    }

    protected final Path originalFolder;
    protected final Path destinationFolder;
    protected final ShowStream out;
    protected final PrintStream err;
    protected final Path sourcepathsListing;
    protected final Path filesListing;
    protected final Path dependenciesListing;
    protected final Path destinationSourcesFolder;
    protected final Path destinationClassesFolder;
    protected final Path destinationJarsFolder;
    protected final List<Path> sourcepaths;
    protected final List<Path> files;
    protected final List<String> dependencies;

    protected final List<CopiedJavaFile> javaFiles;
    protected final CopiedJavaFileHelper javaFileHelper;

    protected final List<CopiedJarFile> jarFiles;
    protected final CopiedJarFileHelper jarFileHelper;

    protected final Map<CopiedJavaFile, Path> sourcepathForJavaFile;
    protected final Map<CopiedJavaFile, JavaName> packageForJavaFile;
    protected final Map<JavaName, Set<Path>> sourcepathsForPackage;
    protected final List<Path> jarsToCopy;
    protected final List<Path> jarsNotCopiedDueToNameCollision;
    protected final List<String> nonJarDependencies;
    protected final Map<JavaName, DecodedDiagnostic> unresolvedQualifiedNames;
    protected final Map<String, DecodedDiagnostic> unresolvedPackages;
    protected final Map<JavaFileObject, Map<String, Set<String>>> unresolvedPackagesForSymbolsBySource;
    protected final Set<Path> suggestedSourcepaths;
    protected final Set<Path> suggestedUnresolvedJavaFiles;
    protected final Set<Path> suggestedJavaFiles;
    protected final Set<Path> suggestedJars;
    protected final Map<String, Integer> codeScores;
    protected CompilationResult compilationResult;

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
        Path originalFolder = null;
        Path destinationFolder = Paths.get("");
        if (i < args.length) {
            originalFolder = Paths.get(args[i]);
            i++;
            if (i < args.length) {
                destinationFolder = Paths.get(args[i]);
                i++;
            }
        }
        if (i < args.length || null == originalFolder) {
            usage(1);
        }

        try {
            return new MinimizeCodeBase(originalFolder, destinationFolder);
        } catch (final IllegalArgumentException e) {
            System.err.println(e.getMessage());
            System.exit(1);
        }
        return null;
    }

    public static void usage() {
        usage(0);
    }

    @SuppressWarnings("resource")
    public static void usage(final int exitStatus) {
        final PrintStream out = 0 == exitStatus ? System.out : System.err;
        for (final String line : USAGE) {
            out.format(line, MinimizeCodeBase.class.getName());
            out.println();
        }
        System.exit(exitStatus);
    }

    protected Path resolveRequiredListing(final String basename) throws IOException {
        return this.resolveAndCheckListing(basename, true);
    }

    protected Path resolveOptionalListing(final String basename) throws IOException {
        return this.resolveAndCheckListing(basename, false);
    }

    protected Path resolveDestinationFolder(final String name) {
        return this.destinationFolder.resolve(name);
    }

    protected Path resolveAndCheckListing(final String basename, final String description, final boolean required)
            throws IOException {
        final Path p = this.destinationFolder.resolve(basename + ".lst");
        if (required) {
            StaticHelpers.checkRequiredFile(p, description);
        } else {
            StaticHelpers.checkRegularFile(p, description);
        }
        return p;

    }

    protected Path resolveAndCheckListing(final String basename, final boolean required) throws IOException {
        return this.resolveAndCheckListing(basename, basename + " listing", required);
    }

    // protected Path getSourcepathForJavaFile(final Path javaFile) {
    // return this.sourcepathForJavaFile.get(javaFile);
    // }

    // protected Set<Path> getSourcepathsForPackage(final String p) {
    // final Set<Path> s = this.sourcepathsForPackage.get(p);
    // if (null == s) {
    // return Collections.emptySet();
    // }
    // return s;
    // }

    protected void inspect(final Object o) {
        this.out.println("----------");
        final Class<? extends Object> c = o.getClass();
        this.out.show(JAVA_KEYWORD_CLASS, o.getClass());
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
            this.out.show(p, n, "...");
        }
        this.out.println("----------");
    }

    private static void showPatternTimes() {
        if (!PATTERN_TIMES.isEmpty()) {
            System.out.println("-- pattern average evaluation times --");
            final Map<String, Long> patternAverages = new HashMap<>();
            for (final Map.Entry<String, List<Long>> entry : PATTERN_TIMES.entrySet()) {
                final String patternName = entry.getKey();
                final List<Long> patternEvaluationTimesNanosec = entry.getValue();
                patternAverages.put(patternName, patternEvaluationTimesNanosec
                        .stream()
                        .mapToLong(Long::longValue)
                        .sum() / patternEvaluationTimesNanosec.size());
            }
            patternAverages
                    .entrySet()
                    .stream()
                    .sorted(Map.Entry.<String, Long>comparingByValue().reversed())
                    .forEach(e -> System.out.format(
                            "%,10d(ns)  %4d(#)  %s%n",
                            e.getValue(),
                            PATTERN_TIMES.get(e.getKey()).size(),
                            e.getKey()));
            System.out.println();
        }
    }

    /**
     * @param sourceFolder
     * @param targetFolder
     * @param files                       relative to sourceFolder
     * @param preserveIntermediateFolders maintain intermediate folders between
     *                                    sourceFolder and copied file, otherwise
     *                                    place file directly in targetFolder
     * @param descriptionSuffix
     * @param copyOptions                 used by
     *                                    {@see java.nio.file.Files#copy(Path, Path,
     *                                    CopyOption...)}
     * @return target paths that were actually copied
     * @throws IOException
     */
    protected Iterable<? extends Path> copyFiles(
            final Path sourceFolder,
            final Path targetFolder,
            final Collection<? extends Path> files,
            final boolean preserveIntermediateFolders,
            final String descriptionSuffix,
            final CopyOption... copyOptions) throws IOException {
        final List<Path> copied = new ArrayList<>(files.size());

        String sourceDesc = "source";
        String targetDesc = "target";
        if (!(null == descriptionSuffix || "".equals(descriptionSuffix))) {
            sourceDesc += " " + descriptionSuffix;
            targetDesc += " " + descriptionSuffix;
        }
        final boolean replaceExisting = Arrays.stream(copyOptions)
                .anyMatch(o -> StandardCopyOption.REPLACE_EXISTING == o);

        this.out.println("ecp  path");
        for (final Path sourceFile : files) {
            final Path resolvedSourceFile = sourceFolder.resolve(sourceFile);
            StaticHelpers.checkRequiredFile(resolvedSourceFile, sourceDesc);

            final Path targetFile = preserveIntermediateFolders ? sourceFile : sourceFile.getFileName();
            final Path resolvedTargetFile = targetFolder.resolve(targetFile);
            StaticHelpers.checkRegularFile(resolvedTargetFile, targetDesc);
            final boolean targetAlreadyExists = Files.exists(resolvedTargetFile);

            final boolean shouldCopy = replaceExisting || !targetAlreadyExists;
            final boolean shouldCreateParents = preserveIntermediateFolders && !targetAlreadyExists;

            this.out.format(
                    "%c%c%c  %s%n",
                    targetAlreadyExists ? 'e' : '.',
                    shouldCopy ? 'c' : '.',
                    shouldCreateParents ? 'p' : '.',
                    sourceFile);
            if (!shouldCopy) {
                continue;
            }
            if (shouldCreateParents) {
                Files.createDirectories(resolvedTargetFile.getParent());
            }
            Files.copy(resolvedSourceFile, resolvedTargetFile, copyOptions);
            copied.add(targetFile);
        }

        this.out.println();
        return copied;
    }

    public static final String JAVA_KEYWORD_CLASS = "class";

    public static final String REGEX_GROUP_NAME_KEYWORD = "keyword";
    public static final String REGEX_GROUP_NAME_PACKAGE = "package";
    public static final String REGEX_GROUP_NAME_SYMBOL = "symbol";
    public static final String REGEX_GROUP_NAME_TYPENAME = "typename";

    public static final String JAVA_IDENTIFIER_REGEX = "\\b\\p{javaJavaIdentifierStart}\\p{javaJavaIdentifierPart}*\\b";
    public static final String JAVA_PACKAGE_REGEX = JAVA_IDENTIFIER_REGEX
            + "(?:\\." + JAVA_IDENTIFIER_REGEX + ")*";
    public static final String JAVA_QUALIFIED_NAME_REGEX = JAVA_IDENTIFIER_REGEX
            + "(?:\\." + JAVA_IDENTIFIER_REGEX + ")+";
    public static final String JAVA_PACKAGE_REGEX_GROUP = "(?<"
            + REGEX_GROUP_NAME_PACKAGE
            + ">"
            + JAVA_PACKAGE_REGEX
            + ")";

    public static final Map<ErrorCode, Map<ErrorCategory, Map<String, Pattern>>> PATTERNS_FOR_COMPILER_ERR;
    static {
        final Map<ErrorCode, Map<ErrorCategory, Map<String, Pattern>>> temp = new LinkedHashMap<>();

        final Map<ErrorCategory, Map<String, Pattern>> doesntExistMap = new LinkedHashMap<>();

        final Map<String, Pattern> packageDoesNotExistMap = new LinkedHashMap<>();
        putPatternForPackageDoesNotExist(
                packageDoesNotExistMap,
                "import",
                "\\bimport\\s+",
                null);
        putPatternForPackageDoesNotExist(
                packageDoesNotExistMap,
                null,
                null,
                null);
        doesntExistMap.put(ErrorCategory.PACKAGE_DOES_NOT_EXIST, packageDoesNotExistMap);

        temp.put(
                ErrorCode.DOESNT_EXIST,
                Collections.unmodifiableMap(doesntExistMap));

        final Map<ErrorCategory, Map<String, Pattern>> cantResolveLocationMap = new LinkedHashMap<>();

        final Map<String, Pattern> cannotFindSymbolMap = new LinkedHashMap<>();
        putPatternForCannotFindSymbolLocation(
                cannotFindSymbolMap,
                ErrorSymbolType.CLASS,
                ErrorLocationType.CLASS,
                JAVA_QUALIFIED_NAME_REGEX);
        putPatternForCannotFindSymbolLocation(
                cannotFindSymbolMap,
                ErrorSymbolType.VARIABLE,
                ErrorLocationType.CLASS,
                JAVA_QUALIFIED_NAME_REGEX);
        // putPatternForCannotFindSymbolLocation(
        // cannotFindSymbolMap,
        // ErrorSymbolType.CLASS,
        // ErrorLocationType.PACKAGE,
        // JAVA_PACKAGE_REGEX_GROUP);
        cantResolveLocationMap.put(
                ErrorCategory.CANNOT_FIND_SYMBOL,
                Collections.unmodifiableMap(cannotFindSymbolMap));

        temp.put(
                ErrorCode.CANT_RESOLVE_LOCATION,
                Collections.unmodifiableMap(cantResolveLocationMap));

        PATTERNS_FOR_COMPILER_ERR = Collections.unmodifiableMap(temp);
    }

    private static void putPatternForPackageDoesNotExist(
            final Map<String, Pattern> map,
            final String contextDescription,
            final String contextPrefixRegex,
            final String contextSuffixRegex) {
        String regex = "\\bpackage\\s+" + JAVA_PACKAGE_REGEX_GROUP + "\\s+does\\s+not\\s+exist\\b";
        if (null != contextDescription) {
            regex += "\\s.*?";
            if (null != contextPrefixRegex) {
                regex += contextPrefixRegex;
            }
            regex += "(?<" + REGEX_GROUP_NAME_TYPENAME + ">"
                    + "\\k<" + REGEX_GROUP_NAME_PACKAGE + ">\\."
                    + "(?<" + REGEX_GROUP_NAME_SYMBOL + ">" + JAVA_IDENTIFIER_REGEX + ")"
                    + ")";
            if (null != contextSuffixRegex) {
                regex += contextSuffixRegex;
            }
        }
        putPattern(map, null != contextDescription ? contextDescription : "no context", regex);
    }

    private static void putPatternForCannotFindSymbolLocation(
            final Map<String, Pattern> map,
            final ErrorSymbolType symbolType,
            final ErrorLocationType locationType,
            final String locationRegexGroup) {
        final String key = String.format("%s in %s", symbolType, locationType);
        final String symbolRegex = String.format(
                "symbol:\\s+(?<%s>%s)\\s+(?<%s>%s)",
                REGEX_GROUP_NAME_KEYWORD,
                symbolType,
                REGEX_GROUP_NAME_SYMBOL,
                JAVA_IDENTIFIER_REGEX);
        final String locationRegex = String.format(
                "location:\\s+%s\\s+%s",
                locationType,
                locationRegexGroup);
        final String regex = "\\bcannot find symbol\\s+"
                + symbolRegex
                + "\\s+"
                + locationRegex;
        putPattern(map, key, regex);
    }

    private static void putPattern(
            final Map<String, Pattern> temp,
            final String key,
            final String regex) {
        temp.put(key, Pattern.compile(regex, Pattern.MULTILINE));
    }

    public static final String JAVA_PACKAGE_STATEMENT_REGEX = "\\bpackage\\s+" + JAVA_PACKAGE_REGEX_GROUP + "\\s*;";
    public static final Pattern JAVA_PACKAGE_STATEMENT_PATTERN = Pattern.compile(JAVA_PACKAGE_STATEMENT_REGEX);

    static interface Showable {
        LinkedHashMap<String, Object> getShowableProperties();
    }

    static class ShowStream extends PrintStream {
        static final String FORMAT = "%s%-20s %s%n";

        public ShowStream(final OutputStream out) {
            super(out);
        }

        public void show(final String prefix, final Showable item) {
            for (final Entry<String, Object> entry : item.getShowableProperties().entrySet()) {
                final Object value = entry.getValue();
                if (null != value) {
                    this.show(prefix, entry.getKey(), value);
                }
            }
        }

        public void show(final Showable item) {
            this.show("", item);
        }

        public void show(final String prefix, final String name, final Object value) {
            this.format(FORMAT, prefix, name, value);
        }

        public void show(final String name, final Object value) {
            this.show("", name, value);
        }
    }

    static class DecodedDiagnostic implements Showable {
        public Diagnostic<? extends JavaFileObject> diag;
        public ErrorCategory category;
        public String pattern;
        public String matched;
        public JavaKeyword keyword;
        public JavaName packageName;
        public JavaName symbol;
        public JavaName typename;

        public DecodedDiagnostic(
                final Diagnostic<? extends JavaFileObject> diag,
                final ErrorCategory category,
                final String pattern,
                final String matched,
                final JavaKeyword keyword,
                final JavaName packageName,
                final JavaName symbol,
                final JavaName typename) {
            this.diag = diag;
            this.category = category;
            this.pattern = pattern;
            this.matched = matched;
            this.keyword = keyword;
            this.packageName = packageName;
            this.symbol = symbol;
            this.typename = typename;
        }

        public DecodedDiagnostic(
                final Diagnostic<? extends JavaFileObject> diag,
                final ErrorCategory category,
                final String pattern,
                final String matched,
                final String keyword,
                final String packageName,
                final String symbol,
                final String typename) {
            this.diag = diag;
            this.category = category;
            this.pattern = pattern;
            this.matched = matched;
            this.keyword = JavaKeyword.fromText(keyword);
            this.packageName = null == packageName ? null : new JavaName(packageName);
            this.symbol = null == symbol ? null : new JavaName(symbol);
            this.typename = null == typename ? null : new JavaName(typename);
        }

        public LinkedHashMap<String, Object> getShowableProperties() {
            final LinkedHashMap<String, Object> x = new LinkedHashMap<>();
            x.put("category", this.category);
            x.put("pattern", this.pattern);
            x.put("keyword", this.keyword);
            x.put("packageName", this.packageName);
            x.put("symbol", this.symbol);
            x.put("typename", this.typename);
            return x;
        }
    }

    public static Map<String, List<Long>> PATTERN_TIMES = new HashMap<>();

    public static List<DecodedDiagnostic> decodeDiagnostic(final Diagnostic<? extends JavaFileObject> diag) {
        final ArrayList<DecodedDiagnostic> details = new ArrayList<>();
        final String[] diagStrings = { diag.toString(), diag.getMessage(null) };
        final Map<ErrorCategory, Map<String, Pattern>> categoryMap = PATTERNS_FOR_COMPILER_ERR
                .getOrDefault(
                        ErrorCode.fromText(diag.getCode()),
                        Collections.emptyMap());
        for (final Map.Entry<ErrorCategory, Map<String, Pattern>> categoryEntry : categoryMap.entrySet()) {
            final ErrorCategory category = categoryEntry.getKey();
            final Map<String, Pattern> patternMap = categoryEntry.getValue();
            final DecodedDiagnostic dd = decodeDiagnosticCategory(
                    diag,
                    diagStrings,
                    category,
                    patternMap);
            if (null != dd) {
                details.add(dd);
            }
        }
        return details;
    }

    /**
     * @return first decoded match in category, or null
     */
    public static DecodedDiagnostic decodeDiagnosticCategory(
            final Diagnostic<? extends JavaFileObject> diag,
            final String[] diagStrings,
            final ErrorCategory category,
            final Map<String, Pattern> patternMap) {
        for (final Map.Entry<String, Pattern> patternEntry : patternMap.entrySet()) {
            final String patternName = patternEntry.getKey();
            final Pattern pattern = patternEntry.getValue();
            final String timesKey = category.text + ", " + patternName;
            for (final String s : diagStrings) {
                final Matcher m = pattern.matcher(s);
                final long before = System.nanoTime();
                final boolean found = m.find();
                final long after = System.nanoTime();
                final long patternEvaluationTimeNanosec = after - before;
                if (!PATTERN_TIMES.containsKey(timesKey)) {
                    PATTERN_TIMES.put(timesKey, new ArrayList<>());
                }
                PATTERN_TIMES.get(timesKey).add(patternEvaluationTimeNanosec);
                if (found) {
                    final DecodedDiagnostic dd = new DecodedDiagnostic(
                            diag,
                            category,
                            patternName,
                            s,
                            valueOfNamedGroup(m, REGEX_GROUP_NAME_KEYWORD),
                            valueOfNamedGroup(m, REGEX_GROUP_NAME_PACKAGE),
                            valueOfNamedGroup(m, REGEX_GROUP_NAME_SYMBOL),
                            valueOfNamedGroup(m, REGEX_GROUP_NAME_TYPENAME));
                    return dd;
                }
            }
        }
        return null;
    }

    public static String valueOfNamedGroup(final Matcher m, final String n) {
        try {
            return m.group(n);
        } catch (final IllegalArgumentException e) {
            return null;
        }
    }

    // public static Path javaNameToPath(final String name, final String... more) {
    // return javaNameToPath(new JavaName(name, more));
    // }

    // public static Path javaNameToPath(final JavaName name) {
    // return Paths.get(javaNameToPathString(name),
    // Arrays
    // .stream(more)
    // .map(MinimizeCodeBase::javaNameToPathString)
    // .toArray(String[]::new));
    // }

    // public static String javaNameToPathString(final String name) {
    // if (null == name) {
    // return null;
    // }
    // return name.replace('.', File.separatorChar);
    // }

    // public static Path javaNameToJavaFile(final String name, final String...
    // more) {
    // return javaNameToJavaFile(new JavaName(name, more));
    // }

    // public static Path javaNameToJavaFile(final JavaName name) {
    // final Path base = javaNameToPath(name);
    // if (null == base) {
    // return null;
    // }
    // final Path parent = base.getParent();
    // Path fileName = base.getFileName();
    // fileName = Paths.get(fileName.toString() +
    // JavaFileObject.Kind.SOURCE.extension);
    // if (null == parent) {
    // return fileName;
    // } else {
    // return parent.resolve(fileName);
    // }
    // }

    public static boolean jarContainsType(final Path jar, final JavaName typeName) {
        final ProcessBuilder pb = new ProcessBuilder(
                "javap",
                "-cp",
                jar.toString(),
                typeName.toString());
        try {
            final Process proc = pb.start();
            return 0 == proc.waitFor();
        } catch (final InterruptedException | IOException e) {
            // TODO Auto-generated catch block
            e.printStackTrace();
            return false;
        }
    }

    // public static List<Path> guessSourcepathFromJavaFile(final Path javaFile) {
    // if (null == javaFile || null == javaFile.getParent()) {
    // return Collections.emptyList();
    // }
    // final ArrayList<Path> guesses = new ArrayList<>();
    // final Path parent = javaFile.getParent();

    // final Optional<String> packageGuess = guessPackageFromJavaFile(javaFile);
    // if (packageGuess.isPresent()) {
    // final Path packageAsPath = javaNameToPath(packageGuess.get());
    // if (parent.endsWith(packageAsPath)) {
    // final Path sourcepathGuess = parent.subpath(0, parent.getNameCount() -
    // packageAsPath.getNameCount());
    // guesses.add(sourcepathGuess);
    // }
    // }
    // return Collections.unmodifiableList(guesses);
    // }

    static enum ErrorCode {
        CANT_RESOLVE_LOCATION("compiler.err.cant.resolve.location"),
        DOESNT_EXIST("compiler.err.doesnt.exist");

        final String text;

        ErrorCode(final String text) {
            this.text = text;
        }

        public String toString() {
            return this.text;
        }

        static ErrorCode fromText(final String text) {
            for (final ErrorCode v : ErrorCode.values()) {
                if (v.text.equals(text)) {
                    return v;
                }
            }
            return null;
        }
    }

    static enum ErrorCategory {
        CANNOT_FIND_SYMBOL("cannot find symbol"),
        PACKAGE_DOES_NOT_EXIST("package does not exist");

        private final String text;

        ErrorCategory(final String text) {
            this.text = text;
        }

        public String toString() {
            return this.text;
        }

        static ErrorCategory fromText(final String text) {
            for (final ErrorCategory v : ErrorCategory.values()) {
                if (v.text.equals(text)) {
                    return v;
                }
            }
            return null;
        }
    }

    static enum ErrorSymbolType {
        CLASS("class"),
        VARIABLE("variable");

        private final String text;

        ErrorSymbolType(final String text) {
            this.text = text;
        }

        public String toString() {
            return this.text;
        }

        static ErrorSymbolType fromText(final String text) {
            for (final ErrorSymbolType v : ErrorSymbolType.values()) {
                if (v.text.equals(text)) {
                    return v;
                }
            }
            return null;
        }
    }

    static enum ErrorLocationType {
        CLASS("class"),
        PACKAGE("package");

        private final String text;

        ErrorLocationType(final String text) {
            this.text = text;
        }

        public String toString() {
            return this.text;
        }

        static ErrorLocationType fromText(final String text) {
            for (final ErrorLocationType v : ErrorLocationType.values()) {
                if (v.text.equals(text)) {
                    return v;
                }
            }
            return null;
        }
    }

    static enum JavaKeyword {
        CLASS("class"),
        PACKAGE("package");

        private final String text;

        JavaKeyword(final String text) {
            this.text = text;
        }

        public String toString() {
            return this.text;
        }

        static JavaKeyword fromText(final String text) {
            for (final JavaKeyword v : JavaKeyword.values()) {
                if (v.text.equals(text)) {
                    return v;
                }
            }
            return null;
        }
    }

    static class JavaName implements Showable {
        final String name;
        final boolean isSimpleName;

        public JavaName(final String first, final String... more) {
            boolean isCompoundName = first.contains(".");
            if (more.length > 0) {
                this.name = first + "." + String.join(".", more);
                isCompoundName = true;
            } else {
                this.name = first;
            }
            this.isSimpleName = !isCompoundName;
        }

        @Override
        public boolean equals(final Object other) {
            if (null != other) {
                if (other instanceof JavaName) {
                    if (this.name.equals(((JavaName) other).name)) {
                        return true;
                    }
                }
            }
            return false;
        }

        @Override
        public int hashCode() {
            return this.name.hashCode();
        }

        @Override
        public String toString() {
            return this.name;
        }

        @Override
        public LinkedHashMap<String, Object> getShowableProperties() {
            final LinkedHashMap<String, Object> r = new LinkedHashMap<>();
            r.put("name", this.name);
            r.put("is simple", this.isSimpleName);
            return r;
        }

        public JavaName resolve(final JavaName other) {
            return new JavaName(this.name, other.name);
        }

        public Path asPath() {
            return Paths.get(this.name.replace('.', File.pathSeparatorChar));
        }

        // public JavaFile asJavaFile() {
        // return Paths.get(this.name.replace('.', File.pathSeparatorChar) +
        // JavaFileObject.Kind.SOURCE.extension);
        // }

        public static JavaName fromFolders(final Path p) {
            if (null == p) {
                return null;
            }
            final int nameCount = p.getNameCount();
            if (nameCount < 1) {
                return null;
            }
            final String first = p.getName(0).toString();
            final String more[] = new String[nameCount - 1];
            for (int i = 1; i < nameCount; i++) {
                final String part = p.getName(i).toString();
                if (part.contains(".")) {
                    throw new IllegalArgumentException(String.format("path has a \".\": %s", p));
                }
                more[i - 1] = part;
            }
            return new JavaName(first, more);
        }
    }

    static class CopiedFile implements Showable {
        final Path originalFolder;
        final Path originalRelative;
        final Path originalResolved;
        final Path destinationFolder;
        final Path destinationRelative;
        final Path destinationResolved;
        final Path fileName;

        CopiedFile(
                final Path originalFolder,
                final Path originalRelative,
                final Path destinationFolder,
                final Path destinationRelative) {
            if (null == originalFolder) {
                throw new NullPointerException("originalFolder");
            }
            if (null == originalRelative) {
                throw new NullPointerException("originalRelative");
            }
            if (null == destinationFolder) {
                throw new NullPointerException("destinationFolder");
            }
            if (null == destinationRelative) {
                throw new NullPointerException("destinationRelative");
            }

            this.originalFolder = originalFolder;
            this.originalRelative = originalRelative;
            this.originalResolved = originalFolder.resolve(originalRelative);
            this.destinationFolder = destinationFolder;
            this.destinationRelative = destinationRelative;
            this.destinationResolved = destinationFolder.resolve(destinationRelative);
            this.fileName = originalRelative.getFileName();
        }

        public LinkedHashMap<String, Object> getShowableProperties() {
            final LinkedHashMap<String, Object> x = new LinkedHashMap<>();
            x.put("originalFolder", this.originalFolder);
            x.put("originalRelative", this.originalRelative);
            x.put("originalResolved", this.originalResolved);
            x.put("destinationFolder", this.destinationFolder);
            x.put("destinationRelative", this.destinationRelative);
            x.put("destinationResolved", this.destinationResolved);
            x.put("fileName", this.fileName);
            return x;
        }

        boolean originalExists() {
            return Files.exists(this.originalResolved);
        }

        boolean destinationExists() {
            return Files.exists(this.destinationResolved);
        }

        boolean copied() {
            return this.originalExists() && this.destinationExists();
        }

        @Override
        public String toString() {
            throw new UnsupportedOperationException();
        }

        String forListing() {
            return StaticHelpers.preparePathForListing(this.originalRelative);
        }
    }

    static class CopiedJavaFile extends CopiedFile {
        final static String EXTENSION = JavaFileObject.Kind.SOURCE.extension;
        final static int EXTENSION_LENGTH = EXTENSION.length();

        final Path relative;
        final JavaName simpleName;
        final Optional<JavaName> packageName;
        final Optional<JavaName> qualifiedName;

        CopiedJavaFile(
                final Path relative,
                final Path originalFolder,
                final Path destinationFolder) {
            super(originalFolder, relative, destinationFolder, relative);
            if (!isJavaSource(relative)) {
                throw new IllegalArgumentException(String.format(
                        "does not end with \"%s\": %s",
                        EXTENSION,
                        relative));
            }
            this.relative = relative;

            final String fileName = this.originalRelative.getFileName().toString();
            final String typeName = fileName.substring(
                    0,
                    fileName.length() - EXTENSION_LENGTH);
            this.simpleName = new JavaName(typeName);
            this.packageName = guessPackageName(this.originalResolved);
            if (this.packageName.isPresent()) {
                this.qualifiedName = Optional.of(this.packageName.get().resolve(this.simpleName));
            } else {
                this.qualifiedName = Optional.empty();
            }
        }

        @Override
        public LinkedHashMap<String, Object> getShowableProperties() {
            final LinkedHashMap<String, Object> x = super.getShowableProperties();
            x.put("simpleName", this.simpleName);
            this.packageName.ifPresent(v -> x.put("packageName", v));
            this.qualifiedName.ifPresent(v -> x.put("qualifiedName", v));
            return x;
        }

        public static boolean isJavaSource(final Path p) {
            return p.getFileName().toString().endsWith(EXTENSION);
        }

        static Optional<JavaName> guessPackageName(final Path resolvedPath) {
            try {
                for (final String line : Files
                        .lines(resolvedPath)
                        .limit(10)
                        .toArray(String[]::new)) {
                    final Matcher m = JAVA_PACKAGE_STATEMENT_PATTERN.matcher(line);
                    if (m.find()) {
                        final String guess = m.group(REGEX_GROUP_NAME_PACKAGE);
                        return Optional.of(new JavaName(guess));
                    }
                }
            } catch (final IOException e) {
            }
            return Optional.empty();
        }
    }

    static class CopiedJavaFileHelper {
        final Path originalFolder;
        final Path destinationFolder;
        final Map<Path, CopiedJavaFile> mapByRelative;

        CopiedJavaFileHelper(final Path originalFolder, final Path destinationFolder) {
            this.originalFolder = originalFolder;
            this.destinationFolder = destinationFolder;

            this.mapByRelative = new LinkedHashMap<>();
        }

        void clear() {
            this.mapByRelative.clear();
        }

        CopiedJavaFile lookup(final JavaFileObject javaFileObject) {
            final Path javaFileObjectPath = Paths.get(javaFileObject.getName());
            if (!javaFileObjectPath.startsWith(this.destinationFolder)) {
                throw new UnsupportedOperationException(String.format(
                        "javaFileObject is not part of this targetFolder%n" +
                                "javaFileObject:  %s%n" +
                                "targetFolder:    %s%n"));
            }
            final Path relative = this.destinationFolder.relativize(javaFileObjectPath);
            return this.lookup(relative);
        }

        CopiedJavaFile lookup(final Path relative) {
            return this.mapByRelative.computeIfAbsent(
                    relative,
                    k -> new CopiedJavaFile(relative, this.originalFolder, this.destinationFolder));
        }
    }

    static class CopiedJarFile extends CopiedFile {
        final static String EXTENSION = ".jar";
        final static int EXTENSION_LENGTH = EXTENSION.length();

        CopiedJarFile(final Path originalFolder, final Path originalRelative, final Path destinationFolder,
                final Path destinationRelative) {
            super(originalFolder, originalRelative, destinationFolder, destinationRelative);
            if (!isJarFile(originalRelative)) {
                throw new IllegalArgumentException(String.format(
                        "does not end with \"%s\": %s",
                        EXTENSION,
                        originalRelative));
            }
        }

        public static boolean isJarFile(final Path p) {
            return p.getFileName().toString().endsWith(EXTENSION);
        }
    }

    static class CopiedJarFileHelper {
        final Path originalFolder;
        final Path destinationFolder;
        final Map<Path, CopiedJarFile> mapByOriginalRelative;

        CopiedJarFileHelper(final Path originalFolder, final Path destinationFolder) {
            this.originalFolder = originalFolder;
            this.destinationFolder = destinationFolder;

            this.mapByOriginalRelative = new LinkedHashMap<>();
        }

        void clear() {
            this.mapByOriginalRelative.clear();
        }

        CopiedJarFile lookup(final Path originalRelative) {
            return this.mapByOriginalRelative.computeIfAbsent(
                    originalRelative,
                    k -> new CopiedJarFile(
                            this.originalFolder,
                            originalRelative,
                            this.destinationFolder,
                            originalRelative.getFileName()));
        }
    }

    static class NullOutputStream extends OutputStream {
        @Override
        public void write(final int b) throws IOException {
        };
    }

    static class ErrorStatistics {
        ErrorStatistics(final Object scope) {
            this.scope = scope;
            this.countsByCode = new LinkedHashMap<>();
        }

        final Object scope;
        final Map<ErrorCode, Integer> countsByCode;

        void add(final ErrorCode code) {
            final Integer count = this.countsByCode.getOrDefault(code, 0);
            this.countsByCode.put(code, count + 1);
        }
    }

    static class CompilationResult {
        CompilationResult(
                final Boolean wasSuccessful,
                final List<Diagnostic<? extends JavaFileObject>> errors) {
            this.wasSuccessful = wasSuccessful;
            this.errors = Collections.unmodifiableList(errors);
            this.statistics = new ErrorStatistics(this);

            final Map<JavaFileObject, ErrorStatistics> tempStatisticsBySource = new LinkedHashMap<>();
            final Map<JavaFileObject, List<Diagnostic<? extends JavaFileObject>>> tempErrorsBySource = new LinkedHashMap<>();
            for (final Diagnostic<? extends JavaFileObject> e : this.errors) {
                final ErrorCode code = ErrorCode.fromText(e.getCode());
                this.statistics.add(code);
                final JavaFileObject source = e.getSource();
                if (!tempErrorsBySource.containsKey(source)) {
                    tempErrorsBySource.put(source, new ArrayList<>());
                }
                tempErrorsBySource.get(source).add(e);
                if (!tempStatisticsBySource.containsKey(source)) {
                    tempStatisticsBySource.put(source, new ErrorStatistics(source));
                }
                tempStatisticsBySource.get(source).add(code);
            }

            this.errorsBySource = Collections.unmodifiableMap(tempErrorsBySource);
            this.statisticsBySource = Collections.unmodifiableMap(tempStatisticsBySource);
        }

        final Boolean wasSuccessful;
        final List<Diagnostic<? extends JavaFileObject>> errors;
        final Map<JavaFileObject, List<Diagnostic<? extends JavaFileObject>>> errorsBySource;
        final ErrorStatistics statistics;
        final Map<JavaFileObject, ErrorStatistics> statisticsBySource;
    }

    static class StaticHelpers {
        static CompilationResult compile(
                final File classOutputFolder,
                final Iterable<? extends File> javaFiles,
                final Iterable<? extends File> sourcepaths,
                final Iterable<? extends File> classpaths)
                throws IOException {
            return compile(
                    classOutputFolder,
                    javaFiles,
                    sourcepaths,
                    classpaths,
                    null,
                    null,
                    null);
        }

        static CompilationResult compile(
                final File classOutputFolder,
                final Iterable<? extends File> javaFiles,
                final Iterable<? extends File> sourcepaths,
                final Iterable<? extends File> classpaths,
                final Writer out,
                final Iterable<String> compilerOptions,
                final Iterable<String> annotationProcessingClasses)
                throws IOException {
            if (null == classOutputFolder) {
                throw new NullPointerException("classOutputDirectory");
            }
            if (null == javaFiles) {
                throw new NullPointerException("javaFiles");
            }

            final DiagnosticCollector<JavaFileObject> collector = new DiagnosticCollector<JavaFileObject>();
            final JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
            final StandardJavaFileManager fileManager = compiler.getStandardFileManager(
                    collector,
                    null,
                    UTF_8);

            // configure file manager
            Files.createDirectories(classOutputFolder.toPath());
            fileManager.setLocation(
                    StandardLocation.CLASS_OUTPUT,
                    Collections.singletonList(classOutputFolder));
            fileManager.setLocation(
                    StandardLocation.SOURCE_PATH,
                    sourcepaths);
            fileManager.setLocation(
                    StandardLocation.CLASS_PATH,
                    classpaths);
            final Iterable<? extends JavaFileObject> javaFileObjectsFromFiles = fileManager
                    .getJavaFileObjectsFromFiles(javaFiles);

            // compile
            final CompilationTask task = compiler.getTask(
                    out,
                    fileManager,
                    collector,
                    compilerOptions,
                    annotationProcessingClasses,
                    javaFileObjectsFromFiles);
            final Boolean wasSuccessful = task.call();
            fileManager.close();

            final List<Diagnostic<? extends JavaFileObject>> errors = collector
                    .getDiagnostics()
                    .stream()
                    .filter(d -> 0 >= Diagnostic.Kind.ERROR.compareTo(d.getKind()))
                    .collect(Collectors.toList());
            final CompilationResult result = new CompilationResult(
                    wasSuccessful,
                    errors);
            return result;
        }

        public static void checkRequiredFile(final Path p, final String description) throws IOException {
            if (!Files.exists(p)) {
                throw new IllegalArgumentException(String.format(
                        "Missing %s file: %s",
                        description,
                        p));
            }
            StaticHelpers.checkRegularFile(p, description);
        }

        public static void checkRegularFile(final Path p, final String description) throws IOException {
            final String guess = StaticHelpers.guessPathType(p);
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
            final String guess = StaticHelpers.guessPathType(p);
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

        public static Iterable<? extends File> asFileIterable(final Stream<? extends Path> paths) {
            return () -> paths.map(Path::toFile).iterator();
        }

        public static Iterable<? extends File> asFileIterable(final Collection<? extends Path> paths) {
            return asFileIterable(paths.stream());
        }

        public static Stream<? extends Path> streamListingWithPaths(final Path listing) throws IOException {
            return StaticHelpers.streamListing(listing).map(Paths::get);
        }

        public static Stream<String> streamListing(final Path listing) throws IOException {
            return Files
                    .lines(listing, UTF_8)
                    .filter(StaticHelpers::isNotCommentLine)
                    .filter(s -> !"".equals(s.trim()));
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

        public static String preparePathForListing(final Path p) {
            return p.toString().replace(File.separatorChar, '/');
        }
    }
}
/*
 * TODO vague thoughts about improvement
 * 
 * avoid suggesting java files with insufficient package info
 * 
 * improve suggestions for each java file by checking if it exists in a known
 * sourcepath
 * 
 */
