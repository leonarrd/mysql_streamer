# -*- coding: utf-8 -*-
class InvalidPositionDictException(Exception):
    pass


class Position(object):
    """ This class makes it flexible to use different types of position in our system.
    Primarily gtid or log position.
    """
    def to_dict(self):
        """This function turns the position object into a dict
        to be saved in database.
        """
        raise NotImplementedError()

    def to_replication_dict(self):
        """This function turns the position object into a dict
        to be used in resuming replication.
        """
        raise NotImplementedError()


class GtidPosition(Position):
    """ This class uses gtid and offset to represent a position.

    Args:
      gtid(str): gtid formatted string.
      offset(int): offset within a pymysqlreplication RowEvent.
    """

    def __init__(self, gtid=None, offset=None):
        super(GtidPosition, self).__init__()
        self.gtid = gtid
        self.offset = offset

    def to_dict(self):
        position_dict = {}
        if self.gtid:
            position_dict["gtid"] = self.gtid
        if self.offset:
            position_dict["offset"] = self.offset
        return position_dict

    def to_replication_dict(self):
        """Turn gtid into auto_position which the param to init pymysqlreplication
        if Position(gtid="sid:13"), then we want auto_position to be "sid:1-14"
        if Position(gtid="sid:13", offset=10), then we want auto_position
        to still be "sid:1-13", skip 10 rows and then resume tailing.
        """
        position_dict = {}
        if self.gtid and self.offset:
            position_dict["auto_position"] = self._format_gtid_set(self.gtid)
        elif self.gtid:
            position_dict["auto_position"] = self._format_next_gtid_set(self.gtid)
        return position_dict

    def _format_gtid_set(self, gtid):
        """This method returns the GTID (as a set) to resume replication handler tailing
        The first component of the GTID is the source identifier, sid.
        The next component identifies the transactions that have been committed, exclusive.
        The transaction identifiers 1-100, would correspond to the interval [1,100),
        indicating that the first 99 transactions have been committed.
        Replication would resume at transaction 100.
        For more info: https://dev.mysql.com/doc/refman/5.6/en/replication-gtids-concepts.html
        """
        sid, transaction_id = gtid.split(":")
        gtid_set = "{sid}:1-{next_transaction_id}".format(
            sid=sid,
            next_transaction_id=int(transaction_id)
        )
        return gtid_set

    def _format_next_gtid_set(self, gtid):
        """Our systems save the last transaction it successfully completed,
        so we add one to start from the next transaction.
        """
        sid, transaction_id = gtid.split(":")
        return "{sid}:1-{next_transaction_id}".format(
            sid=sid,
            next_transaction_id=int(transaction_id) + 1
        )


class LogPosition(Position):
    """ This class uses log_pos, log_file and offset to represent a position.

    Args:
      log_pos(int): the log position on binlog.
      log_file(string): binlog name.
      offset(int): offset within a pymysqlreplication RowEvent.
    """

    def __init__(self, log_pos=None, log_file=None, offset=None):
        self.log_pos = log_pos
        self.log_file = log_file
        self.offset = offset

    def to_dict(self):
        position_dict = {}
        if self.log_pos and self.log_file:
            position_dict["log_pos"] = self.log_pos
            position_dict["log_file"] = self.log_file
        if self.offset:
            position_dict["offset"] = self.offset
        return position_dict

    def to_replication_dict(self):
        position_dict = {}
        if self.log_pos and self.log_file:
            position_dict["log_pos"] = self.log_pos
            position_dict["log_file"] = self.log_file
        return position_dict


def construct_position(position_dict):
    if "gtid" in position_dict:
        return GtidPosition(
            gtid=position_dict.get("gtid"),
            offset=position_dict.get("offset", None)
        )
    elif "log_pos" in position_dict and "log_file" in position_dict:
        return LogPosition(
            log_pos=position_dict.get("log_pos"),
            log_file=position_dict.get("log_file"),
            offset=position_dict.get("offset", None)
        )
    else:
        raise InvalidPositionDictException


class HeartbeatPosition(LogPosition):
    """ The location of a MySQL heartbeat event inside a log file
    Contains additional information about the heartbeat such as its
    sequence number and date-time. """

    def __init__(self, hb_serial, hb_timestamp, log_pos, log_file, offset=0):
        super(HeartbeatPosition, self).__init__(log_pos, log_file, offset)
        self.hb_serial, self.hb_timestamp = hb_serial, hb_timestamp

    def __str__(self):
        return "Serial:     {}\nTimestamp:  {}\nFile:       {}\nPosition:   {}".format(
            self.hb_serial, self.hb_timestamp, self.log_file, self.log_pos
        )

    def __eq__(self, other):
        return (self.hb_serial == other.hb_serial and
                self.hb_timestamp == other.hb_timestamp and
                self.log_file == other.log_file and
                self.log_pos == other.log_pos)
