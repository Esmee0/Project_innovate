# ai_predictor.py

from sklearn.ensemble import RandomForestRegressor
from datetime import date
import numpy as np


class DurationPredictor:

    def __init__(self):
        self.model = RandomForestRegressor(
            n_estimators=100,
            random_state=42
        )
        self.trained = False

    def train(self, assignments, worklogs):
        """
        Train model op historische opdrachten.
        """

        X = []
        y = []

        for assignment in assignments:

            logs = [
                wl for wl in worklogs
                if wl.assignment_id == assignment.id
            ]

            total_hours = sum(wl.hours_done for wl in logs)

            if total_hours <= 0:
                continue

            duration_days = max(
                1,
                (assignment.due_date - assignment.start_date).days
            )

            title_length = len(assignment.title)

            X.append([
                duration_days,
                title_length
            ])

            y.append(total_hours)

        # needs 3 assignments in the data to be able to predict 
        if len(X) < 3:
            self.trained = False
            return False

        self.model.fit(X, y)

        self.trained = True
        return True

    def predict(self, title, start_date, due_date):

        if not self.trained:
            return None

        duration_days = max(
            1,
            (due_date - start_date).days
        )

        title_length = len(title)

        features = [[
            duration_days,
            title_length
        ]]

        prediction = self.model.predict(features)[0]

        return round(max(1.0, prediction), 1)


predictor = DurationPredictor()


