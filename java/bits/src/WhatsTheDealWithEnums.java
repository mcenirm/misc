import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

import javax.tools.Diagnostic;
import javax.tools.Diagnostic.Kind;

public class WhatsTheDealWithEnums {
    public static void main(final String[] args) {
        System.out.println("yo");
        for (final WhatsTheDealWithEnums.Color c : Color.values()) {
            System.out.format(
                    "%7s %7s %7d %7s %7s%n",
                    c,
                    c.name(),
                    c.ordinal(),
                    c.toString(),
                    c.rgb);
        }
        System.out.println(Color.fromRGB("#f00"));
        System.out.println("--------------------");
        for (final Kind k : Diagnostic.Kind.values()) {
            System.out.format(" %d %s%n", k.ordinal(), k.name());
        }
    }

    static enum Color {
        RED("#f00"),
        GREEN("#0f0"),
        BLUE("#00f");

        final String rgb;

        Color(final String rgb) {
            this.rgb = rgb;
        }

        final static Map<String, Color> rgbToColor;
        static {
            final HashMap<String, Color> temp = new HashMap<>();
            for (final Color c : Color.values()) {
                temp.put(c.rgb, c);
            }
            rgbToColor = Collections.unmodifiableMap(temp);
        }

        static Color fromRGB(final String rgb) {
            return rgbToColor.get(rgb);
        }
    }
}
