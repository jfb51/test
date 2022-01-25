import numpy as np


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

