import collections
import typing


class SimpableUser(object):

    all_simpable_users: typing.Dict[int, typing.Dict[int, 'SimpableUser']] = collections.defaultdict(dict)
    __slots__ = ('user_id', 'guild_id', '_simping_for', '_being_simped_by')

    def __init__(self, user_id:int, guild_id:int):
        self.user_id: int = user_id
        self.guild_id: int = guild_id
        self._simping_for: typing.Set[int] = set()
        self._being_simped_by: typing.Set[int] = set()
        self.all_simpable_users[self.guild_id][self.user_id] = self

    def add_simping_for(self, uid:int) -> None:
        self._simping_for.add(uid)

    def add_being_simped_by(self, uid:int) -> None:
        self._being_simped_by.add(uid)

    def remove_simping_for(self, uid:int) -> None:
        self._simping_for.discard(uid)

    def remove_being_simped_by(self, uid:int) -> None:
        self._being_simped_by.discard(uid)

    @property
    def simping_for(self) -> typing.Set['SimpableUser']:
        return set([self.get_simpable_user(i, self.guild_id) for i in self._simping_for])

    @property
    def being_simped_by(self) -> typing.Set['SimpableUser']:
        return set([self.get_simpable_user(i, self.guild_id) for i in self._being_simped_by])

    @classmethod
    def get_simpable_user(cls, user_id:int, guild_id:int) -> 'SimpableUser':
        """Get a SimpableUser object for the given member"""

        v = cls.all_simpable_users[guild_id].get(user_id)
        if v is None:
            return cls(user_id, guild_id)
        return v
