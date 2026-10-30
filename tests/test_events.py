import numpy as np
import pandas as pd
from socceraction.spadl import config
from socceraction.xthreat import ExpectedThreat, move_transition_matrix

from pipeline.events import cell, native_xy, possession_goals, role


def actions():
    return pd.DataFrame({"start_x":[0.,0.,52.5],"start_y":[34.,34.,34.],"end_x":[105.,105.,52.5],"end_y":[34.,34.,34.],
                         "type_id":[config.actiontypes.index("pass")]*3,"result_id":[config.results.index("success"),config.results.index("fail"),config.results.index("success")]})


def test_boundary_cells_are_in_range():
    assert cell(0,0)==(11,0)
    assert cell(105,68)==(0,15)
    assert cell(-1,100)==(0,0)


def test_native_coordinate_conversion():
    assert native_xy([120,80])==(105,68)
    assert native_xy([0,0])==(0,0)
    assert native_xy(None) is None


def test_failed_moves_retain_transition_mass():
    transition = move_transition_matrix(actions())
    nonzero = transition.sum(axis=1)
    assert np.isclose(nonzero.max(),1)
    assert any(np.isclose(nonzero,.5))
    assert (nonzero<=1).all()


def test_same_cell_has_zero_value_and_failures_unrated():
    model = ExpectedThreat()
    model.xT = np.tile(np.linspace(.01,.30,16),(12,1))
    ratings = model.rate(actions())
    assert ratings[0] > 0
    assert np.isnan(ratings[1])
    assert ratings[2] == 0


def test_shootouts_excluded_from_possession_labels():
    events = [{"period":1,"possession":1}, {"period":1,"possession":1,"shot":{"outcome":{"name":"Goal"}}},
              {"period":5,"possession":2,"shot":{"outcome":{"name":"Goal"}}}]
    assert dict(possession_goals(events)) == {1:1}


def test_role_mapping_does_not_call_all_players_forwards():
    assert role("Left Center Back")=="Centre back"
    assert role("Left Wing Back")=="Full back"
    assert role("Center Attacking Midfield")=="Midfielder"
    assert role("Goalkeeper")=="Goalkeeper"
