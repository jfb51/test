import numpy as np
from collections import namedtuple


def kelly_bet(row, comission=0.05, bankroll=1000):
    if row.side == "None":
        return 0
    elif row.side == 'Back':
        d = row.decimal_offer
        p = row.estimated_probability_lower
        f = (p * (d - 1) * (1 - comission) - (1 - p)) / ((d - 1) * (1 - comission))
        return bankroll * np.minimum(f, 1)
    else:
        d = row.decimal_bid
        p = row.estimated_probability_upper
        f = ((1 - p) * (1 - comission) - p * (d - 1)) / ((d - 1) * (1 - comission))
        return -bankroll * np.minimum(f, 1 / (d - 1))


def slim_regression_model(models):
    slim_reg = namedtuple('slim_reg', ['condition', 'model_variables', 'lookup_dict'])
    slim_models = []
    for model in models:
        slim_models.append(slim_reg(model.condition, model.model_variables, model.lookup_dict))
    return slim_models


def match_row(match_id, match_df):
    return match_df.loc[str(match_id)].to_dict()


def match_data(match_id, bbb_df):
    return bbb_df[lambda x: x.match_id == match_id].sort_values(['innings',
                                                                 'legal_balls_in_innings_b4b', 'innings_runs_b4b'])


def careers(match_id, career_df):
    return career_df.xs(match_id, level=1)
