import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParseProblemException;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.TypeDeclaration;
import com.github.javaparser.utils.Log;

class FindJavaMains {

    final static String[] MAIN_DECLARATION_VALUES = {
            "public static void main(String[])",
            "public static void main(java.lang.String[])",
    };
    final static Set<String> MAIN_DECLARATIONS = Collections
            .unmodifiableSet(new HashSet<>(Arrays.asList(MAIN_DECLARATION_VALUES)));

    public static void main(final java.lang.String[] args) throws IOException {
        final ArrayList<Path> starts = new ArrayList<>();
        int argi = 0;
        while (argi < args.length) {
            if ("--".equals(args[argi])) {
                argi++;
                break;
            } else if (args[argi].startsWith("-")) {
                System.err.print("Usage: ");
                System.err.print(FindJavaMains.class.getName());
                System.err.println(" [start ...]");
                System.err.println("Find Java source files with main-capable classes");
                System.err.println("Where:");
                System.err.println("  start    starting directory (current directory by default)");
                System.exit(1);
            } else {
                starts.add(Paths.get(args[argi]));
                argi++;
            }
        }
        while (argi < args.length) {
            starts.add(Paths.get(args[argi]));
            argi++;
        }
        if (starts.size() < 1) {
            starts.add(Paths.get("."));
        }

        Log.setAdapter(new Log.StandardOutStandardErrorAdapter());
        final JavaParser parser = new JavaParser();

        for (final Path start : starts) {
            Files.find(start, Integer.MAX_VALUE, FindJavaMains::isJavaSourceFile)
                    .forEach(path -> {
                        try {
                            final CompilationUnit cu = parser.parse(path).getResult().get();
                            final String relativePathAsString = start.relativize(path).toString();
                            for (final TypeDeclaration<?> t : cu.getTypes()) {
                                final String qualifiedName = t.getFullyQualifiedName().get();
                                boolean hasUsableMain = false;
                                for (final MethodDeclaration m : t.getMethodsByName("main")) {
                                    final String d = m.getDeclarationAsString(true, false, false);
                                    if (MAIN_DECLARATIONS.contains(d)) {
                                        hasUsableMain = true;
                                        break;
                                    }
                                }
                                if (hasUsableMain) {
                                    System.out.print(start);
                                    System.out.print(File.separator);
                                    System.out.print(relativePathAsString);
                                    System.out.print("\t");
                                    System.out.print(qualifiedName);
                                    System.out.println();
                                }
                            }
                        } catch (final ParseProblemException | IOException e) {
                        }
                    });
        }
    }

    public static boolean isJavaSourceFile(final Path p, final BasicFileAttributes bfa) {
        return p.toFile().getName().toLowerCase(Locale.ROOT).matches(".*\\.java");
    }
}
