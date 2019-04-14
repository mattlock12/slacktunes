CREATE DATABASE IF NOT EXISTS slacktunes_dev;
CREATE USER 'slacktuner'@'localhost' IDENTIFIED BY 'slacktuner';
GRANT ALL ON `slacktunes_dev`.* TO `slacktuner`@`localhost`;