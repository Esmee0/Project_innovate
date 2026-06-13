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
        