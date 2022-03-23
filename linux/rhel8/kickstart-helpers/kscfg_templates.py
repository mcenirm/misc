TEMPLATES = {}

TEMPLATES[
    "experiment1"
] = """
# Install from installation media
cdrom

# Set default language
lang en_US.UTF-8

# Set keyboard type / layout
keyboard us

# Configure network
network --onboot yes --hostname={fqdn} --bootproto=static --ip={ip} --netmask={netmask} --gateway={gateway} --nameserver {nameservers_comma_sep}

# Set root password
rootpw --iscrypted {rootpw}

# Enable firewall
firewall --enabled --ssh

# Set authentication options
authconfig --enableshadow --passalgo=sha512

# Enforce SELinux
selinux --enforcing

# Set time zone
timezone --utc {timezone}

# Set bootloader with OSPP SSG kernel parameters
bootloader --location=mbr --append="audit=1 audit_backlog_limit=8192 slub_debug=P page_poison=1 vsyscall=none"

# Format all disks
zerombr

# Remove Linux partitions
clearpart --linux --initlabel

# Create primary system partitions (required for installs)
part /boot --fstype=xfs --size=1024
part pv.01 --grow --size=1

# Create LVM group
volgroup {volgroup_name} --pesize=4096 pv.01

# Create logical volumes
logvol swap --name=swap --vgname={volgroup_name} --size={swapsize}
logvol / --fstype=xfs --name=root --vgname={volgroup_name} --size=10240

# OSPP SSG partition isolation
logvol /home          --name=home        --fstype=xfs --vgname={volgroup_name} --size=1024 --fsoptions="nodev"
logvol /tmp           --name=tmp         --fstype=xfs --vgname={volgroup_name} --size=1024 --fsoptions="nodev,nosuid,noexec"
logvol /var           --name=var         --fstype=xfs --vgname={volgroup_name} --size=3072 --fsoptions="nodev"
logvol /var/log       --name=varlog      --fstype=xfs --vgname={volgroup_name} --size=1024 --fsoptions="nodev,nosuid,noexec"
logvol /var/log/audit --name=varlogaudit --fstype=xfs --vgname={volgroup_name} --size=512  --fsoptions="nodev,nosuid,noexec"
logvol /var/tmp       --name=vartmp      --fstype=xfs --vgname={volgroup_name} --size=1024 --fsoptions="nodev,nosuid,noexec"

# Enable OSPP SSG
%addon org_fedora_oscap
        content-type = scap-security-guide
        profile = xccdf_org.ssgproject.content_profile_ospp
%end

# Packages selection
%packages
@Base
%end

# Reboot after installation
reboot --eject
"""

TEMPLATES[
    "experiment2"
] = """
# Install from installation media
cdrom

# Set default language
lang en_US.UTF-8

# Set keyboard type / layout
keyboard us

# Configure network
network --onboot yes --hostname={fqdn} --bootproto=static --ip={ip} --netmask={netmask} --gateway={gateway} --nameserver {nameservers_comma_sep}

# Set root password
rootpw --iscrypted {rootpw}

# Enable firewall
firewall --enabled --ssh

# Enforce SELinux
selinux --enforcing

# Set time zone
timezone --utc {timezone}

# Set bootloader with OSPP SSG kernel parameters
bootloader --location=mbr --append="audit=1 audit_backlog_limit=8192 slub_debug=P page_poison=1 vsyscall=none"

# Format all disks
zerombr

# Remove Linux partitions
clearpart --linux --initlabel

# Create primary system partitions (required for installs)
part /boot/efi --fstype=efi --size=200
part /boot     --fstype=xfs --size=1024
part pv.01 --grow --size=1

# Create LVM group
volgroup {volgroup_name} --pesize=4096 pv.01

# Create logical volumes
logvol swap --name=swap --vgname={volgroup_name} --size={swapsize}
logvol / --fstype=xfs --name=root --vgname={volgroup_name} --size=10240

# OSPP SSG partition isolation
logvol /home          --name=home        --fstype=xfs --vgname={volgroup_name} --size=1024 --fsoptions="nodev"
logvol /tmp           --name=tmp         --fstype=xfs --vgname={volgroup_name} --size=1024 --fsoptions="nodev,nosuid,noexec"
logvol /var           --name=var         --fstype=xfs --vgname={volgroup_name} --size=3072 --fsoptions="nodev"
logvol /var/log       --name=varlog      --fstype=xfs --vgname={volgroup_name} --size=1024 --fsoptions="nodev,nosuid,noexec"
logvol /var/log/audit --name=varlogaudit --fstype=xfs --vgname={volgroup_name} --size=512  --fsoptions="nodev,nosuid,noexec"
logvol /var/tmp       --name=vartmp      --fstype=xfs --vgname={volgroup_name} --size=1024 --fsoptions="nodev,nosuid,noexec"

# Enable OSPP SSG
%addon org_fedora_oscap
        content-type = scap-security-guide
        profile = xccdf_org.ssgproject.content_profile_ospp
%end

# Packages selection
%packages
@Base
%end

# Reboot after installation
reboot --eject
"""

PARAMETER_NAMES_TO_COPY = set(
    [
        "gateway",
        "ip",
        "netmask",
        "rootpw",
        "swapsize",
        "timezone",
    ]
)


def prepare_template_parameters(machine: dict) -> dict:
    p = {}
    for k in PARAMETER_NAMES_TO_COPY:
        p[k] = machine[k]
    p["nameservers_comma_sep"] = ",".join(machine["nameservers"])
    p["volgroup_name"] = "rhel_" + machine["name"]
    p["fqdn"] = machine["name"] + "." + machine["domain"]
    return p
