import numpy as np
import pandas as pd
import itertools
from collections import defaultdict


class RegressionBasedModel:
    def __init__(self, condition, model, prefill=False):
        self.condition = condition
        self.model = model
        self.model_data = self.model.model.data.orig_exog
        self.model_variables = [s.strip() for s in self.model.model.data.formula.split('~')[1].split('+')]
        self.model_params = self.model.params.to_dict()
        if 'formula' in self.model.model.__dir__():
            self.model.model.data.frame = model.model.data.frame[:10]
        if prefill:
            self.lookup_dict = self.prefill_predictions_from_formula()
        else:
            self.lookup_dict = {}

    def prefill_predictions_from_formula(self):
        # model space = lambda function to filter the model
        # model hyperparams = for a model, which variables do I split by
        # sane values dict = hardcoded ranges of the values e.g. overs have to be 1-20 inclusive
        df = self.model_data
        if 'Intercept' in df.columns:
            df = df.drop(['Intercept'], axis=1)
            f = lambda x: self.model.model.predict(self.model.params, exog=np.array([(1,) + x]))
        else:
            f = lambda x: self.model.model.predict(self.model.params, exog=np.array([x]))
        #         if len(df.columns) > 1:
        lol = []
        if len(df.columns) > 1:
            for column in df.columns:
                unique_values = pd.unique(df[column])
                lol.append(unique_values)
                exog_combinations = list(itertools.product(*lol))
        else:
            exog_combinations = np.unique(df)
        # potential messiness with categoricals remains.
        # probably want to turn these tuples into namedtuples.
        model_input = {}
        model_predictions = CustomDefaultDict(f)
        if type(self.model.model).__name__ != 'OrderedModel':
            if len(df.columns) > 1:
                for i, column in enumerate(df.columns):
                    # if created from a formula, we have to predict in a different way.
                    model_input[column] = [c[i] for c in exog_combinations]
            else:
                model_input[df.columns[0]] = exog_combinations
            predictions = self.model.predict(model_input).values
        else:
            predictions = self.model.predict(exog_combinations)
        model_predictions.update(dict(zip(exog_combinations, predictions)))
        return model_predictions


class CustomDefaultDict(defaultdict):
    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError((key,))
        self[key] = value = self.default_factory(key)
        return value