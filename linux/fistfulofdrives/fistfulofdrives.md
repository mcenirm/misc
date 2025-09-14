Planning notes

 * research needed
   * how to automount when USB device appears, without desktop env
     * <https://unix.stackexchange.com/a/11478>
 * when a drive is plugged in:
   * warn if any drive has more than one partition
   * warn if any partition is not in expected fstype list (ext4, ...)
   * use LABEL and UUID to identify volumes
   * what to do if we saw this volume before?
   * capture listing (hashdeep?)
 * file copying/filtering ideas
   * how to configure destination?
   * should we try to archive batches of directories?
   * how to select files in batches?
