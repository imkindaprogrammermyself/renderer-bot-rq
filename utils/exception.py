class VersionNotFoundError(Exception):
    pass


class ReadingError(Exception):
    pass


class RenderingError(Exception):
    pass


class UnsupportedBattleTypeError(Exception):
    pass


class MultipleReplaysError(Exception):
    pass


class NotEnoughReplaysError(Exception):
    pass


class ArenaIdMismatchError(Exception):
    pass