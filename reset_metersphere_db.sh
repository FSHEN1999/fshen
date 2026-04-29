#!/bin/sh
/usr/bin/docker exec mysql sh -lc 'mysql -uroot -p"Password123@mysql" --protocol=TCP -h127.0.0.1 -P3306 -e "SHOW DATABASES;"'
/usr/bin/docker exec mysql sh -lc 'mysql -uroot -p"Password123@mysql" --protocol=TCP -h127.0.0.1 -P3306 -e "DROP DATABASE IF EXISTS metersphere; CREATE DATABASE metersphere DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"'
