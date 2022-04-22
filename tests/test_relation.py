import overpy
from matplotlib import pyplot as plt

from pyridy.osm.utils import OSMRelation


def test_osmrelation():
    api = overpy.Overpass()
    query = """
        <union>
            <query type="relation">
                <has-kv k="name" v="2600 Köln Hbf - Aachen Süd Grenze"/>
            </query>
            <recurse type="relation-node" into="nodes"/>
            <recurse type="relation-way"/>
            <recurse type="way-node"/>
        </union>
        <print/>
    """

    result = api.query(query)

    rel = result.relations[0]
    rel_way_ids = [mem.ref for mem in rel.members if type(mem) == overpy.RelationWay and not mem.role]
    rel_ways = [w for w in result.ways if w.id in rel_way_ids]

    sort_order = {w_id: idx for w_id, idx in zip(rel_way_ids, range(len(rel_way_ids)))}
    rel_ways.sort(key=lambda w: sort_order[w.id])

    relation = OSMRelation(relation=rel, ways=rel_ways)

    fig, axs = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    axs[0].plot(relation.tracks[0].s, relation.tracks[0].c)
    axs[0].set_ylim([-0.01, 0.01])
    axs[0].grid()
    axs[0].set_xlabel('Distance [m]')
    axs[0].set_ylabel('Curvature [1/m]')

    axs[1].plot(relation.tracks[1].s, relation.tracks[1].c)
    axs[1].set_ylim([-0.01, 0.01])
    axs[1].grid()
    axs[1].set_xlabel('Distance [m]')
    axs[1].set_ylabel('Curvature [1/m]')

    plt.show()

    assert True
