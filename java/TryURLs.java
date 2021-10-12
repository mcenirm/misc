import java.io.IOException;
import java.lang.System.Logger;
import java.lang.System.Logger.Level;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;

import javax.net.ssl.HttpsURLConnection;

public class TryURLs {
    private static Logger LOG = System.getLogger(Foo.class.getName());

    public static void show(String name, Object value) {
        LOG.log(Level.INFO, "{0}:  \"{1}\"", name, value);
    }

    public static void main(String[] args) {
        for (var a : args) {
            show("argument", a);
            try {
                var u = new URL(a);
                show("url", u);
                var c = u.openConnection();
                show("connection", c);
                if (c instanceof HttpURLConnection) {
                    var httpc = (HttpURLConnection) c;
                    httpc.setRequestMethod("GET");
                }
                c.connect();
                if (c instanceof HttpsURLConnection) {
                    var https = (HttpsURLConnection) c;
                    var peer = https.getPeerPrincipal();
                    show("peer", peer);
                }
                if (c instanceof HttpURLConnection) {
                    var httpc = (HttpURLConnection) c;
                    int code = httpc.getResponseCode();
                    show("status code", code);
                }
            } catch (MalformedURLException e) {
                LOG.log(Level.ERROR, e);
            } catch (IOException e) {
                LOG.log(Level.ERROR, e);
            }
        }
    }
}