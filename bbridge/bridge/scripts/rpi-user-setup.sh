
USER="bridge"
PASSWORD="t00f@r"

useradd --create-home --user-group $USER
echo -e "$PASSWORD\n$PASSWORD\n" | sudo passwd $USER

adduser bridge sudo
adduser bridge adm

# Switch to the bridge user
su $USER
echo $PASSWORD

deluser pi
rm /home/pi
