#!/usr/bin/env bash
# Create a Linux user on an AlmaLinux EC2 instance and authorize an SSH public key for it.
#
# Usage (run on the instance):
#   sudo ./add-ssh-user.sh <username> "<ssh-public-key>" [--sudo]
#
# Example:
#   sudo ./add-ssh-user.sh ec2-user "ssh-ed25519 AAAAC3Nz... me@laptop" --sudo
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run as root (use sudo)." >&2
  exit 1
fi

if [[ $# -lt 2 ]]; then
  echo "Usage: sudo $0 <username> \"<ssh-public-key>\" [--sudo]" >&2
  exit 1
fi

USERNAME="$1"
PUBKEY="$2"
GRANT_SUDO="${3:-}"

if ! [[ "$PUBKEY" =~ ^(ssh-(rsa|ed25519|dss)|ecdsa-sha2-nistp(256|384|521)|sk-(ssh-ed25519|ecdsa-sha2-nistp256)@openssh\.com)\  ]]; then
  echo "That does not look like an SSH public key (paste the contents of your .pub file)." >&2
  exit 1
fi

if id "$USERNAME" &>/dev/null; then
  echo "User '$USERNAME' already exists; adding key to it."
else
  useradd -m -s /bin/bash "$USERNAME"
  echo "Created user '$USERNAME'."
fi

HOME_DIR="$(getent passwd "$USERNAME" | cut -d: -f6)"
SSH_DIR="$HOME_DIR/.ssh"
AUTH_KEYS="$SSH_DIR/authorized_keys"

install -d -m 700 -o "$USERNAME" -g "$USERNAME" "$SSH_DIR"
touch "$AUTH_KEYS"
if grep -qxF "$PUBKEY" "$AUTH_KEYS"; then
  echo "Key already present in $AUTH_KEYS."
else
  echo "$PUBKEY" >> "$AUTH_KEYS"
  echo "Key added to $AUTH_KEYS."
fi
chown "$USERNAME:$USERNAME" "$AUTH_KEYS"
chmod 600 "$AUTH_KEYS"

# AlmaLinux runs SELinux in enforcing mode; wrong contexts make sshd ignore authorized_keys.
if command -v restorecon &>/dev/null; then
  restorecon -R "$SSH_DIR"
fi

if [[ "$GRANT_SUDO" == "--sudo" ]]; then
  usermod -aG wheel "$USERNAME"
  echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-$USERNAME"
  chmod 440 "/etc/sudoers.d/90-$USERNAME"
  visudo -cf "/etc/sudoers.d/90-$USERNAME" >/dev/null
  echo "Granted passwordless sudo to '$USERNAME'."
fi

echo "Done. From your laptop: ssh -i <path-to-private-key> $USERNAME@<instance-public-ip>"
