from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestRegressor
import numpy as np
from datetime import datetime, date

class DurationPredictor:

    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features= 10)

        self.model= RandomForestRegressor(n_estimators= 10, random_state= 42)
        self.is_trained = False

    
    def train(self, assignment, worklogs):
        if not assignment or not worklogs:
            return False
        
        X_text = []
        X_numerical = []
        y = []

        for assignment in assignments:
            logs = [wl for wl in worklogs if wl.assignment_id == assignment.id]

            if not logs:
                continue 


            total_hours = sum(wl.hours_done for wl in logs)

            if  total_hours <= 0:
                continue

            X_text.append(assignment.title)

            days_available = (assignment.due_date - assignment.start_date).days

            days_since_start - (date.today() - assignment.start_date).days

            X_numerical.append([days_available, day_since_start])
            y.append(total_hours)

        if len(X_text) < 2:
            return False
        
        X_text_features = self.vectorizer.fit_transform(X_text).toarray()

        X= np.hstack([X_text_features, X_numerical])

        self.model.fit(x, y)
        self.is_trained = True
        return True
    
    
    def predict(self, title, start_date, due_date):
        if not self.is_trained:
            return None
        try:
            X_text_features = self.vectorizer.transform([title]).toarray()

            days_available = (due_date - start_date).days
            days_since_start = (date.today() - start_date).days

            X_numerical = np.array([[days_available, days_since_start]])

            X = np.hstack([X_text_features, X_numerical])

            prediction = self.model.predict(X)[0]

            return max(0.5, prediction)
        
        except Exception as e:
            print(f"prediction error: {e}")
            return None
        
predictor = DurationPredictor


