-- Get latest check-in for each computer
--  cf https://stackoverflow.com/a/1313140

CREATE VIEW computerlatestcheckin AS
    SELECT *
    FROM records
    INNER JOIN (
        SELECT computer, max(timestamp) AS maxtimestamp
        FROM records
        GROUP BY computer
    ) AS r2
    ON (records.computer = r2.computer AND records.timestamp = r2.maxtimestamp);
