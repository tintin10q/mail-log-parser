# mail-log-parser

A script to figure out all recipients for messages received from a specific SMTP client host
in Postfix logs.


## Examples 

To generate a csv file with data run:

```shell
python parse_email_logs.py mail.log mail.log.1 mail.log.2.gz  mail.log.3.gz mail.log.4.gz --csv-header > emails.csv
```

See which emails adresses where send to: 

```shell
python parse_email_logs.py mail.log --output-cols to --output-unique  > emails.txt
```

## Help text

```text
usage: parse_email_logs.py [-h] [--host HOST] [--csv-header]
                           [--dsn-prefix DSN_PREFIX] [--invert-dsn-prefix]
                           [--output-mode {csv,json}]
                           [--output-cols {timestamp,queue_id,client_host,client_ip,from,to,orig_to,relay,dsn,status,size}
                                          [{timestamp,queue_id,client_host,client_ip,from,to,orig_to,relay,dsn,status,size} ...]]
                           [--output-unique]
                           files [files ...]

Extract all recipients for messages received from a specific SMTP client host
in Postfix logs.

positional arguments:
  files                 Log files to parse (supports .gz).

options:
  -h, --help            show this help message and exit
  --host HOST           SMTP client hostname to match (default:
                        mx.hok.vologda.su)
  --csv-header          Print CSV header.
  --dsn-prefix DSN_PREFIX
                        Only output rows with this dsn prefix (2. is success)
  --invert-dsn-prefix   Only output that do not start with --dsn-prefix.
  --output-mode {csv,json}
  --output-cols {timestamp,queue_id,client_host,client_ip,from,to,orig_to,relay,dsn,status,size} [{timestamp,queue_id,client_host,client_ip,from,to,orig_to,relay,dsn,status,size} ...]
                        Choose output columns seperated by spaces, by default
                        outputs everything
  --output-unique       Only output unique rows from the rows you selected
```
