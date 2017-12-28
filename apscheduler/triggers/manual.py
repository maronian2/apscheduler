from apscheduler.triggers.base import BaseTrigger

class ManualTrigger(BaseTrigger):
    """
    Trigger never fires. Function get_next_fire_time always returns None
    
    Jobs with this trigger can ONLY be triggered manually
    """
    __slots__ = ()
    def __init__(self, timezone=None):
        pass

    def get_next_fire_time(self, previous_fire_time, now):
        """
        Always returns ``None``

        :param datetime.datetime previous_fire_time: the previous time the trigger was fired
        :param datetime.datetime now: current datetime
        """
        return None

    def __str__(self):
        return 'manual'

    def __repr__(self):
        return "<%s ()>" % (self.__class__.__name__)
