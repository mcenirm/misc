import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;
import java.net.URLConnection;
import java.security.Principal;
import java.security.cert.Certificate;
import java.security.cert.CertificateParsingException;
import java.security.cert.X509Certificate;
import java.util.Collection;
import java.util.Date;
import java.util.List;

import javax.net.ssl.HttpsURLConnection;

public class TryURLs {
    public static void show(String prefix, String name, Object value) {
        System.out.format("%s%-14s  %s%n", prefix, name, value);
    }

    public static void show(String name, Object value) {
        show("", name, value);
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
                    Certificate[] certificates = https.getServerCertificates();
                    for (int i = 0; i < certificates.length; i++) {
                        show("certificate", i);
                        if (certificates[i] instanceof X509Certificate) {
                            String p = "  ";
                            X509Certificate x509 = (X509Certificate) certificates[i];
                            Date notAfter = x509.getNotAfter();
                            show(p, "not after", notAfter);
                            Principal issuer = x509.getIssuerDN();
                            show(p, "issuer", issuer);
                            Principal subject = x509.getSubjectDN();
                            show(p, "subject", subject);
                            try {
                                Collection<List<?>> sans = x509.getSubjectAlternativeNames();
                                if (null != sans) {
                                    String pp = "    ";
                                    for (List<?> san : sans) {
                                        int sanType = (Integer) san.get(0);
                                        String sanTypeName = SANTypeNames[sanType];
                                        Object sanValue = san.get(1);
                                        show(pp, sanTypeName, sanValue);
                                    }
                                }
                            } catch (CertificateParsingException e) {
                                show(p, "exception", e);
                            }
                        }
                    }
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

    public static final String[] SANTypeNames = {
            "otherName",
            "rfc822Name",
            "dNSName",
            "x400Address",
            "directoryName",
            "ediPartyName",
            "uniformResourceIdentifier",
            "iPAddress",
            "registeredID",
    };

    public static final String[] SANValueTypes = {
            "OtherName",
            "IA5String",
            "IA5String",
            "ORAddress",
            "Name",
            "EDIPartyName",
            "IA5String",
            "OCTET STRING",
            "OBJECT IDENTIFIER",
    };

}
