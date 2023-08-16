import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;
import java.net.URLConnection;
import java.security.Principal;

import javax.net.ssl.HttpsURLConnection;

public class TryURLs {
    public static void show(String name, Object value) {
        System.out.format("%-14s  %s%n", name, value);
    }

    public static void main(String[] args) {
        String separatorLine = "----------------------------------------";
        for (String a : args) {
            System.out.println(separatorLine);
            show("argument", a);
            try {
                URL u = new URL(a);
                show("url", u);
                URLConnection c = u.openConnection();
                show("connection", c);
                HttpURLConnection httpc;
                if (c instanceof HttpURLConnection) {
                    httpc = (HttpURLConnection) c;
                    httpc.setRequestMethod("GET");
                }
                c.connect();
                if (c instanceof HttpsURLConnection) {
                    HttpsURLConnection https = (HttpsURLConnection) c;
                    Principal peer = https.getPeerPrincipal();
                    show("peer", peer);
                }
                if (c instanceof HttpURLConnection) {
                    httpc = (HttpURLConnection) c;
                    int code = httpc.getResponseCode();
                    show("status code", code);
                }
            } catch (MalformedURLException e) {
                show("exception", e);
            } catch (IOException e) {
                show("exception", e);
            }
        }
        System.out.println(separatorLine);
    }
}
