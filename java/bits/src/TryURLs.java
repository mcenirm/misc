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
    public static void show(final String prefix, final String name, final Object value) {
        System.out.format("%s%-14s  %s%n", prefix, name, value);
    }

    public static void show(final String name, final Object value) {
        show("", name, value);
    }

    public static void main(final String[] args) {
        final String separatorLine = "----------------------------------------";
        for (final String a : args) {
            System.out.println(separatorLine);
            show("argument", a);
            try {
                final URL u = new URL(a);
                show("url", u);
                final URLConnection c = u.openConnection();
                show("connection", c);
                HttpURLConnection httpc;
                if (c instanceof HttpURLConnection) {
                    httpc = (HttpURLConnection) c;
                    httpc.setRequestMethod("GET");
                }
                c.connect();
                if (c instanceof HttpsURLConnection) {
                    final HttpsURLConnection https = (HttpsURLConnection) c;
                    final Principal peer = https.getPeerPrincipal();
                    show("peer", peer);
                    final Certificate[] certificates = https.getServerCertificates();
                    for (int i = 0; i < certificates.length; i++) {
                        show("certificate", i);
                        if (certificates[i] instanceof X509Certificate) {
                            final String p = "  ";
                            final X509Certificate x509 = (X509Certificate) certificates[i];
                            final Date notAfter = x509.getNotAfter();
                            show(p, "not after", notAfter);
                            final Principal issuer = x509.getIssuerDN();
                            show(p, "issuer", issuer);
                            final Principal subject = x509.getSubjectDN();
                            show(p, "subject", subject);
                            try {
                                final Collection<List<?>> sans = x509.getSubjectAlternativeNames();
                                if (null != sans) {
                                    final String pp = "    ";
                                    for (final List<?> san : sans) {
                                        final int sanType = (Integer) san.get(0);
                                        final String sanTypeName = SANTypeNames[sanType];
                                        final Object sanValue = san.get(1);
                                        show(pp, sanTypeName, sanValue);
                                    }
                                }
                            } catch (final CertificateParsingException e) {
                                show(p, "exception", e);
                            }
                        }
                    }
                }
                if (c instanceof HttpURLConnection) {
                    httpc = (HttpURLConnection) c;
                    final int code = httpc.getResponseCode();
                    show("status code", code);
                }
            } catch (final MalformedURLException e) {
                show("exception", e);
            } catch (final IOException e) {
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
