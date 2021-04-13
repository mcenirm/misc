## Unable to install miniconda on amazonlinux2

```console
$ bash Miniconda3-py39_4.9.2-Linux-x86_64.sh -b -f -p $HOME/mc3
PREFIX=/home/ec2-user/mc3
Unpacking payload ...
/home/ec2-user/mc3/conda.exe: error while loading shared libraries: libz.so.1: failed to map segment from shared object
/home/ec2-user/mc3/conda.exe: error while loading shared libraries: libz.so.1: failed to map segment from shared object
```

According to https://admin-ahead.com/portal/knowledgebase/4/error-while-loading-shared-libraries-libzso1-failed-to-map-segment-from-shared-object-Operation-not-permitted.html this is caused by `/tmp` being mounted `noexec`.

```console
$ mount | grep /tmp
tmpfs on /var/tmp type tmpfs (rw,nosuid,nodev,noexec,relatime)
tmpfs on /tmp type tmpfs (rw,nosuid,nodev,noexec,relatime)
```

They identify a workaround of setting the `TMP` environment variable, but `TMPDIR` seems to be the relevant one.

```console
$ export TMPDIR=$XDG_RUNTIME_DIR/tmp
$ mkdir $TMPDIR
$ bash Miniconda3-py39_4.9.2-Linux-x86_64.sh -b -f -p $HOME/mc3
PREFIX=/home/ec2-user/mc3
Unpacking payload ...
Collecting package metadata (current_repodata.json): done
Solving environment: done

[...]
```
