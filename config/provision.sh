#!/bin/bash
#
# This script sets things up and is supposed to be run on the first boot of a
# new server. It is specifically supposed to be used as a Linode StackScript,
# hence these user-defined variables:
#
# <UDF name="hostname" Label="Hostname" default="solo" />
# <UDF name="user" Label="Username" default="josh" />
# <UDF name="pass" Label="Password" />
# <UDF name="db_pass" Label="Password" />
# <UDF name="transportapi_app_id" Label="Transport API app id" />
# <UDF name="transportapi_app_key" Label="Transport API app key" />

export DEBIAN_FRONTEND=noninteractive

# determine IP address of this server
IP=$(dig +short myip.opendns.com @resolver1.opendns.com)

# set hostname
echo "$HOSTNAME" > /etc/hostname
hostname -F /etc/hostname
echo "$IP $HOSTNAME.bustimes.org.uk $HOSTNAME" >> /etc/hosts

# set timezone to London
ln -fs /usr/share/zoneinfo/Europe/London /etc/localtime
dpkg-reconfigure -f noninteractive tzdata

# add normal user
adduser --disabled-password --gecos "" "$USER"
adduser "$USER" sudo
# echo "Added user '$USER'"

echo "$USER:$PASS" | chpasswd
# echo "Set $USER's password to '$PASS'"

# use local mirrors
sed -i 's/us.archive.ubuntu.com/gb.archive.ubuntu.com/g' /etc/apt/sources.list

apt-get update -yqq
apt-get upgrade -yqq

# install nginx
apt-get install -yqq nginx
echo "Installed nginx"

# configure nginx
sed -i 's/# server_tokens off;/server_tokens off;/' /etc/nginx/nginx.conf;
service nginx reload
echo "Configured nginx"

# add my public key
su -l "$USER" -c "
mkdir -p .ssh
echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDJrBT3fmXwfNJlyy4+vZhBmMxWZLVW3JkMdxq4Duxu85YRMMfkdD36zqOC3XbFaM/RqZL76t9lEyucOMUNxO3aw4Ok41XS6mt7n6Fa1Q8Sgf3kK6l/P0MVeb/oNc2svkllrfap1C0WRGLZC3gd/+95DitYenkjSJy7Rnl06/xqFXRxSaRLLn5ZKFNGBdiwzqcF5FCJCVjr6uaBtJ8GmL3vHaSTo1aNa2JQiGJS1ZloF15XWu03FiTXuMvHZIkbNqBsMkEf8STwJM5hU0eB/mOufuMFS6jqYL1AcC910w8fvYDtTEDuyHXdxBbyiBg1YEg+yDyiEJsoCAcjRm9fKjsf ' >> .ssh/authorized_keys
chmod 600 .ssh/authorized_keys
"
echo "Added public key"

# set up nice things
echo  "bind '\"\e[A\":history-search-backward'
bind '\"\e[B\":history-search-forward'" >> /home/"$USER"/.bashrc

# configure ssh
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
service ssh restart
echo "Configured sshd"

# install elasticsearch
wget -qO - https://packages.elastic.co/GPG-KEY-elasticsearch | apt-key add -
echo "deb https://packages.elastic.co/elasticsearch/2.x/debian stable main" > /etc/apt/sources.list.d/elasticsearch-2.x.list
apt-get update -yqq
apt-get install -yqq openjdk-8-jre-headless elasticsearch
# systemctl enable elasticsearch.service

# install git, postfix, postgres, python, etc
apt-get install -yqq git postfix ruby-sass npm
apt-get install -yqq python3-pip python3-dev libpq-dev postgresql postgresql-contrib postgis
pip3 install virtualenv

ln -s "$(which nodejs)" /usr/bin/node

# set up database
su postgres -c "
createdb bustimes
echo 'create extension postgis' | psql bustimes
echo \"create user bustimes with password '$DB_PASS'\" | psql
echo 'grant all privileges on database bustimes to bustimes' | psql
"

su -l "$USER" -c "
# clone git repositroy
git clone https://github.com/jclgoodwin/bustimes.org.uk.git
cd bustimes.org.uk

# set up python virtualenv, install python dependancies
virtualenv -p python3 env
. env/bin/activate
pip install -r requirements.txt
pip install -r requirements-prod.txt
pip install gunicorn

export SECRET_KEY=f

npm install yuglify bower
cd busstops/static/js
../../../node_modules/.bin/bower install
cd ../../..
./manage.py collectstatic
./manage.py sendtestemail --admin
"

echo "[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=$USER
Group=www-data
WorkingDirectory=/home/$USER/bustimes.org.uk
ExecStart=/home/$USER/bustimes.org.uk/env/bin/gunicorn --config=file:gunicorn-config.py buses.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s TERM $MAINPID

[Install]
WantedBy=multi-user.target
" > /etc/systemd/system/bustimes.service
systemctl enable bustimes
