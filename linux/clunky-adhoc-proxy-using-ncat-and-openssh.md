Choose a pair of available TCP ports (local, remote).
These can be the same number, since they are on different systems.
The examples below use distinct numbers for clarity
(local = 10287, remote = 10289).

1. In one terminal, run "ncat" as an HTTP proxy:

    ```shell
    ncat -l --proxy-type http 127.0.0.1 10287
    ```

2. In a second terminal, "ssh" to the remote system, with remote port forwarding:

    ```shell
    ssh -R 127.0.0.1:10289:127.0.0.1:10287 REMOTESYSTEM
    ```

3. On the remote system, configure proxy environment variables:

    ```shell
    export http_proxy=127.0.0.1:10289
    export https_proxy=$http_proxy
    ```

Note: This can be in a new terminal, or in the shell session from step 2.

Most subsequent commands in that same session should use the proxy, but it will depend on the specific program.

<hr>

The following command combines all of the above into a single scary invocation, but it doesn't gracefully support complex arguments to the "ssh" command:

```shell
bash -c 'p=10288 ; lh=127.0.0.1 ; ncat -l --proxy-type http $lh $p & ncpid=$! ; ssh -t -R $lh:$p:$lh:$p "$@" "export {http,https}_proxy=$lh:$p ; bash -il" ; kill $ncpid' -- REMOTESYSTEM
```

<hr>

A previous approach tried using dynamic remote port forwarding,
in which the OpenSSH client acts as a SOCKS5 proxy,
which was added in OpenSSH 7.6 (`-R` with just a port number).
Important clients, notably `wget`, do not support SOCKS5.
