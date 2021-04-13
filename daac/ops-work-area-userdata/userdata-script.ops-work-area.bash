#!/bin/bash
set -euo pipefail
set -x
yum update -y

# core ops work area requirements
yum -y install at bash bzip2 coreutils diffutils file findutils gawk glibc.i686 grep gzip ncompress perl-Digest-SHA psmisc screen sed tar tree util-linux

# EFS client requirements
yum -y install amazon-efs-utils jq

# miscellaneous
yum -y install https://downloads.rclone.org/rclone-current-linux-amd64.rpm

# detect account configuration and set variables
INTERNAL_BUCKET=$(aws s3 ls | sort -r | egrep -o '\w+-internal$' | tail -n1)
REGION=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | jq .region -r)
DATA_FS=$(aws ssm get-parameter --region $REGION --name ghrc-ops-work-area-data-share-fs --output text --query Parameter.Value)
DATA_MOUNT=/data

# install GHRC local tools
aws s3 cp s3://"$INTERNAL_BUCKET"/packages/ghrc-local-tools/ghrc-local-tools-master.tar.gz - | tar xz --strip-components=1 --no-same-owner -f - -C /usr/local/ ghrc-local-tools-master/tools/

# configure EFS
cat >> /etc/fstab <<EOF
$DATA_FS:/  $DATA_MOUNT  efs  _netdev,noresvport,tls,iam  0 0
EOF
mkdir -pv -- "$DATA_MOUNT"
mount -v -- "$DATA_MOUNT"
