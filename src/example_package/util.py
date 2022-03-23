import numpy as np
from collections import namedtuple, OrderedDict
from math import erf
from operator import itemgetter

def kelly_bet(row, commission=0.05, bankroll=1000):
    if row.side == "None":
        return 0
    elif row.side == 'Back':
        d = row.decimal_offer
        p = row.estimated_probability_lower
        f = (p * (d - 1) * (1 - commission) - (1 - p)) / ((d - 1) * (1 - commission))
        return bankroll * np.minimum(f, 1)
    else:
        d = row.decimal_bid
        p = row.estimated_probability_upper
        f = ((1 - p) * (1 - commission) - p * (d - 1)) / ((d - 1) * (1 - commission))
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


def phi(z):
    return 0.5 * (1.0 + erf(z/1.41421356237))


def categorify_dict(state):
    #todo: I think the ordering is unnecessary?
    dy = state.copy()
    for k, v in state.items():
        if type(v) == str:
            new_k = k + '[T.' + v + ']'
            dy[new_k] = 1
            del dy[k]
    return OrderedDict(sorted(dy.items()))


def remove_useless_regression_model_params(state, params):
    #todo: I think the ordering is unnecessary?
    smol = params.copy()
    for param in params.keys():
        if param not in state.keys():
            del smol[param]
    return OrderedDict(sorted(smol.items()))


def remove_useless_regression_model_params_multinomial(state, params):
    smol = OrderedDict()
    for outcome, p in params.items():
        smoler = p.copy()
        for param in p.keys():
            if param not in state.keys():
                del smoler[param]
        smol[outcome] = OrderedDict(sorted(smoler.items()))
    return smol


def calculate_probit_model_probability(reg, model):
    items = itemgetter(*model.model_variables)(reg)
    dz = dict(zip(model.model_variables, items))
    dz['Intercept'] = 1
    state = categorify_dict(dz)
    relevant_params = remove_useless_regression_model_params(state, model.model_params)
    z = sum(state[key] * relevant_params[key] for key in state)
    return phi(z)


def calculate_mnlogit_model_probabilities(reg, model):
    items = itemgetter(*model.model_variables)(reg)
    dz = dict(zip(model.model_variables, items))
    dz['Intercept'] = 1
    state = categorify_dict(dz)
    relevant_params = remove_useless_regression_model_params_multinomial(state, model.model_params)
    exp_sum = []
    for k, v in relevant_params.items():
        exp_sum.append(2.71828**(sum(v[param] * state[param] for param in v.keys())))
    p_dot = 1 / (1 + sum(exp_sum))
    p_one = p_dot * exp_sum[0]
    p_two = p_dot * exp_sum[1]
    p_three = p_dot * exp_sum[2]
    p_four = p_dot * exp_sum[3]
    p_six = p_dot * exp_sum[4]

    return [p_dot, p_one, p_two, p_three, p_four, p_six]

