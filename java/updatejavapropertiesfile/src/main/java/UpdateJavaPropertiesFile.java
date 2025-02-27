import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.apache.commons.configuration2.FileBasedConfiguration;
import org.apache.commons.configuration2.PropertiesConfiguration;
import org.apache.commons.configuration2.builder.FileBasedConfigurationBuilder;
import org.apache.commons.configuration2.builder.fluent.Parameters;
import org.apache.commons.configuration2.convert.DefaultListDelimiterHandler;
import org.apache.commons.configuration2.ex.ConfigurationException;

/**
 * TODO: Support commenting out an item?
 */
public class UpdateJavaPropertiesFile {

    public static void usage() {
        System.out.println("Usage: " + UpdateJavaPropertiesFile.class.getName() + " PROPERTIESFILE NAME=VALUE [...]");
    }

    public static void usageAndExit() {
        usage();
        System.exit(1);
    }

    public static void main(final String[] args) {
        final List<String> words = new ArrayList<>(Arrays.asList(args));

        while (!words.isEmpty()) {
            final String word = words.get(0);
            if ("--" == word) {
                words.remove(0);
            } else if (word.startsWith("-")) {
                usageAndExit();
            }
            break;
        }
        if (words.isEmpty()) {
            usageAndExit();
        }

        final String propertiesFilename = words.remove(0);
        if (words.isEmpty()) {
            usageAndExit();
        }

        final ArrayList<Map<String, String>> updates = new ArrayList<>();

        final Pattern nameEqualValuePattern = Pattern.compile("^([^=]+)=(.*)$");
        while (!words.isEmpty()) {
            final String arg = words.remove(0);

            final Matcher m = nameEqualValuePattern.matcher(arg);
            if (m.matches()) {
                final String name = m.group(1);
                final String value = m.group(2);
                final Map<String, String> map = new HashMap<>();
                map.put(name, value);
                updates.add(map);
                continue;
            } else {
                System.err.println("Error: Bad update format: " + arg);
                System.exit(1);
            }
        }

        final Parameters params = new Parameters();
        final FileBasedConfigurationBuilder<FileBasedConfiguration> builder = new FileBasedConfigurationBuilder<FileBasedConfiguration>(
                PropertiesConfiguration.class)
                .configure(
                        params
                                .properties().setFileName(propertiesFilename));
        // .setListDelimiterHandler(new DefaultListDelimiterHandler(',')));
        try {
            final FileBasedConfiguration config = builder.getConfiguration();
            for (final Map<String, String> update : updates) {
                for (final Entry<String, String> item : update.entrySet()) {
                    final String name = item.getKey();
                    final String value = item.getValue();
                    config.setProperty(name, value);
                }
            }
            builder.save();
        } catch (final ConfigurationException e) {
            System.err.println(e.getLocalizedMessage());
            System.exit(1);
        }
    }
}
