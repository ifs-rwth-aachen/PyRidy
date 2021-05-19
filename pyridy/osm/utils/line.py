from pyridy.osm.utils import OSMTrack


class OSMRailwayLine(OSMTrack):
    def __init__(self, id: int, ways: list, tags: dict, members: list):
        super().__init__(id=id, ways=ways, name=tags.get("name", ""), color=tags.get("colour", "#FFFFFF"))
        self.__dict__.update(tags)
        self.members = members

    def __repr__(self):
        return self.__dict__.get("name", "")
