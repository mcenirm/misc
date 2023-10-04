import java.io.File;
import java.io.IOException;
import java.io.Writer;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.FileTime;
import java.util.Locale;

import javax.tools.DiagnosticListener;
import javax.tools.JavaCompiler;
import javax.tools.JavaCompiler.CompilationTask;
import javax.tools.JavaFileObject;
import javax.tools.JavaFileObject.Kind;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

/**
 * A class that conditionally recompiles itself
 */
public class RecompileSelf {
    public static void main(String[] args) throws IOException {
        recompile(RecompileSelf.class, () -> {
            System.out.println("Recompiled self. Exiting. Run again.");
        }, () -> {
            System.out.println("Did not need to recompile self.");
        });
    }

    public static void recompile(final Class<?> clazz, Runnable ifRecompiled, Runnable ifNotRecompiled)
            throws IOException {
        if (shouldRecompile(clazz)) {
            compile(clazz);
            ifRecompiled.run();
        } else {
            ifNotRecompiled.run();
        }
    }

    public static void recompile(final Class<?> clazz, Runnable ifRecompiled) throws IOException {
        recompile(clazz, ifRecompiled, () -> {
        });
    }

    public static void recompile(final Class<?> clazz) throws IOException {
        recompile(clazz, () -> {
        });
    }

    public static boolean shouldRecompile(final Class<?> clazz) throws IOException {
        return shouldRecompile(asFile(clazz, Kind.SOURCE), asFile(clazz, Kind.CLASS));
    }

    public static boolean shouldRecompile(final File sourceFile, final File classFile)
            throws IOException {
        Path sourceFilePath = sourceFile.toPath();
        Path classFilePath = classFile.toPath();
        if (!Files.exists(classFilePath)) {
            return true;
        }
        FileTime mtimeSource = Files.getLastModifiedTime(sourceFilePath);
        FileTime mtimeClass = Files.getLastModifiedTime(classFilePath);
        return mtimeSource.compareTo(mtimeClass) > 0;
    }

    public static boolean compile(final Class<?> clazz, Writer out,
            DiagnosticListener<? super JavaFileObject> diagnosticListener, Locale locale, Charset charset,
            Iterable<String> options)
            throws IOException {
        File file = asFile(clazz, Kind.SOURCE);
        final JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        final StandardJavaFileManager fileManager = compiler.getStandardFileManager(diagnosticListener, locale,
                charset);
        final Iterable<? extends JavaFileObject> javaFiles = fileManager.getJavaFileObjects(file);
        final CompilationTask task = compiler.getTask(out, fileManager, diagnosticListener, options, null, javaFiles);
        try {
            return task.call();
        } finally {
            fileManager.close();
        }
    }

    public static boolean compile(final Class<?> clazz, Writer out) throws IOException {
        return compile(clazz, out, null, null, null, null);
    }

    public static boolean compile(final Class<?> clazz) throws IOException {
        return compile(clazz, null);
    }

    public static File asFile(final Class<?> clazz, Kind kind) {
        return new File(clazz.getName() + kind.extension);
    }
}
