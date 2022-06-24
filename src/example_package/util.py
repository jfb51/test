import numpy as np
from collections import namedtuple, OrderedDict
from math import erf
from operator import itemgetter
import bisect


class SlimRegModel:
    def __init__(self, condition, model):
        self.condition = condition
        self.model_variables = [s.strip() for s in model.model.data.formula.split('~')[1].split('+')]
        self.model_params = model.params.to_dict()
        if 'bowling_style_bowl' in self.model_variables:
            self.model_params['bowling_style_bowl[T.right_arm_seam]'] = 0
        if 'event_name' in self.model_variables:
            self.model_params['event_name[T.Bangladesh Premier League]'] = 0
        if 'playing_role_bowl' in self.model_variables:
            self.model_params['playing_role_bowl[T.Allrounder]'] = 0
        self.model_params = OrderedDict(sorted(self.model_params.items()))


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
    return career_df.xs(match_id, level=1).droplevel(1).to_dict(orient='index')


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
    return smol


def remove_useless_regression_model_params_multinomial(state, params):
    smol = {}
    for outcome, p in params.items():
        smoler = p.copy()
        for param in p.keys():
            if param not in state.keys():
                del smoler[param]
        smol[outcome] = smoler
    return smol


def calculate_probit_model_probability(reg, model):
    items = itemgetter(*model.model_variables)(reg)
    if len(model.model_variables) == 1:
        items = [items]
    dz = dict(zip(model.model_variables, items))
    dz['Intercept'] = 1
    state = categorify_dict(dz)
    relevant_params = remove_useless_regression_model_params(state, model.model_params)
    z = sum(state[key] * relevant_params[key] for key in state)
    return phi(z)


def calculate_logit_model_probability(reg, model):
    if len(model.model_variables) == 1:
        if model.model_variables == ['1']:
            dz = dict()
        else:
            items = itemgetter(*model.model_variables)(reg)
            items = [items]
            dz = dict(zip(model.model_variables, items))
    else:
        items = itemgetter(*model.model_variables)(reg)
        dz = dict(zip(model.model_variables, items))
    dz['Intercept'] = 1
    state = categorify_dict(dz)
    relevant_params = remove_useless_regression_model_params(state, model.model_params)
    exp_sum = 2.71828**(sum(state[key] * relevant_params[key] for key in state))
    p_fail = 1 / (1 + exp_sum)
    p_success = 1 - p_fail

    return p_success


def calculate_mnlogit_model_probabilities(reg, model):
    if len(model.model_variables) == 1:
        if model.model_variables == ['1']:
            dz = dict()
        else:
            items = itemgetter(*model.model_variables)(reg)
            items = [items]
            dz = dict(zip(model.model_variables, items))
    else:
        items = itemgetter(*model.model_variables)(reg)
        dz = dict(zip(model.model_variables, items))
    dz['Intercept'] = 1
    state = categorify_dict(dz)
    relevant_params = remove_useless_regression_model_params_multinomial(state, model.model_params)
    exp_sum = []
    for k, v in relevant_params.items():
        exp_sum.append(2.71828**(sum(v[param] * state[param] for param in v.keys())))
    p_dot = 1 / (1 + sum(exp_sum))
    other_run_p = [p_dot]
    for i in range(len(exp_sum)):
        other_run_p.append(p_dot * exp_sum[i])

    return other_run_p


def find_le(a, x):
    'Find rightmost value less than or equal to x'
    i = bisect.bisect_right(a, x)
    if i:
        return a[i-1]
    raise ValueError


def update_career_bowling(bowling_dict):
    for k, v in list(bowling_dict.items()):
        if k.startswith('overs_bowled_after') or k.endswith('prev_match_bowl'):  # this is now 2 matches ago...
            del bowling_dict[k]

    for k, v in list(bowling_dict.items()):
        if k.startswith('bowled_over'):
            eh = bowling_dict.pop(k)
            bowling_dict['{}_prev_match_bowl'.format(k[:-5])] = eh

    for k, v in list(bowling_dict.items()):
        if type(bowling_dict[k]) != str:
            if np.isnan(bowling_dict[k]):
                bowling_dict[k] = 0

    bowling_dict['cum_dots_bowl'] += bowling_dict['dots_bowl']
    bowling_dict['cum_balls_bowled_bowl'] += bowling_dict['balls_bowled_bowl']
    bowling_dict['cum_wickets_b4m_bowl'] = bowling_dict['cum_wickets']
    for c in ['ones', 'twos', 'threes', 'fours', 'sixes', 'wides', 'nbs']:
        bowling_dict['cum_{}_bowl'.format(c)] += bowling_dict['{}_conceded_bowl'.format(c)]
        bowling_dict['prop_{}_bowl'.format(c)]: bowling_dict['cum_{}_bowl'.format(c)] / bowling_dict[
            'cum_balls_bowled_bowl']
    for i in range(1, 21):
        bowling_dict['cum_overs_{}_bowl'.format(i)] += bowling_dict['bowled_over_{}_prev_match_bowl'.format(i)]
    bowling_dict['cum_mid_overs_bowl'] += bowling_dict['middle_overs_bowled_bowl']
    if bowling_dict['cum_mid_overs_bowl'] > 0:
        bowling_dict['prop_mid_bowl'] = 6 * bowling_dict['cum_mid_overs_bowl'] / bowling_dict['cum_balls_bowled_bowl']
    else:
        bowling_dict['prop_mid_bowl'] = 0
    for s in ['pp', 'death']:
        bowling_dict['cum_{}_overs_bowl'.format(s)] += bowling_dict['{}_overs_bowled_bowl'.format(s)]
        if bowling_dict['cum_{}_overs_bowl'.format(s)] > 0:
            bowling_dict['prop_{}_bowl'.format(s)] = 6 * bowling_dict['cum_{}_overs_bowl'.format(s)] / bowling_dict[
                'cum_balls_bowled_bowl']
        else:
            bowling_dict['prop_{}_bowl'.format(s)] = 0
    #         bowling_dict['economy_rate_bowl'] = /bowling_dict['cum_balls_bowled_bowl']
    if bowling_dict['cum_wickets_b4m_bowl'] > 0:
        bowling_dict['strike_rate_bowl'] = bowling_dict['cum_balls_bowled_bowl'] / bowling_dict['cum_wickets_b4m_bowl']
    else:
        bowling_dict['strike_rate_bowl'] = 0
    # the ewms have not been updated, nor has the "shit rating", cbf with the economy rate for now.
    return bowling_dict


def update_career_batting(batting_dict):
    for k, v in list(batting_dict.items()):
        if type(batting_dict[k]) != str:
            if np.isnan(batting_dict[k]):
                batting_dict[k] = 0
    batting_dict['cum_balls_bat'] += batting_dict['balls_orig_bat']
    batting_dict['cum_outs_b4m'] = batting_dict['cum_outs']
    for c in ['dots', 'ones', 'twos', 'threes', 'fours', 'sixes']:
        batting_dict['cum_{}_bat'.format(c)] += batting_dict['{}_bat'.format(c)]
        if batting_dict['cum_balls_bat'] > 0:
            batting_dict['prop_{}_bat'.format(c)] = batting_dict['cum_{}_bat'.format(c)]/batting_dict['cum_balls_bat']
        else:
            batting_dict['prop_{}_bat'.format(c)] = 0
    if batting_dict['cum_balls_bat'] > 0:
        batting_dict['out_per_ball'] = batting_dict['cum_outs_b4m']/batting_dict['cum_balls_bat']
    else:
        batting_dict['out_per_ball'] = 0
    #the ewms have not been updated, nor has the "shit rating".
    return batting_dict