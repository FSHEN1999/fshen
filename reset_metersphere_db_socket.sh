#!/bin/sh
/usr/bin/docker exec mysql sh -lc 'mysql -uroot -p"Password123@mysql" --protocol=SOCKET --socket=/var/run/mysqld/mysqld.sock -e "DROP DATABASE IF EXISTS metersphere; CREATE DATABASE metersphere DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"'
