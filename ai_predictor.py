# ai_predictor.py
"""
Simple AI predictor zonder scikit-learn - werkt overal!
Baseert voorspelling op:
1. Aantal dagen tot deadline
2. Historische gemiddelde uren per dag
3. Sleutelwoorden in de titel
"""

from datetime import date

class DurationPredictor:
    """Eenvoudige predictor gebaseerd op regels en historie"""
    
    def __init__(self):
        self.average_hours_per_day = 5.0  # Default
        self.keyword_multipliers = {
            "project": 1.5,
            "essay": 1.0,
            "homework": 0.8,
            "test": 0.5,
            "exam": 2.0,
            "coding": 2.0,
            "presentation": 1.2,
            "research": 1.5,
            "report": 1.3,
            "assignment": 1.0,
        }
    
    def train(self, assignments, worklogs):
        """
        Train op historische data.
        Berekent gemiddelde uren per dag.
        """
        if not assignments or not worklogs:
            return False
        
        total_hours = 0
        total_days = 0
        
        for assignment in assignments:
            logs = [wl for wl in worklogs if wl.assignment_id == assignment.id]
            if not logs:
                continue
            
            hours = sum(wl.hours_done for wl in logs)
            if hours <= 0:
                continue
            
            days = (assignment.due_date - assignment.start_date).days
            if days <= 0:
                days = 1
            
            total_hours += hours
            total_days += days
        
        if total_days > 0:
            self.average_hours_per_day = max(1.0, total_hours / total_days)
        
        return total_hours > 0
    
    def predict(self, title, start_date, due_date):
        """
        Voorspel uren op basis van:
        - Aantal dagen beschikbaar
        - Gemiddelde uren per dag
        - Sleutelwoorden in titel
        """
        
        # Bereken aantal beschikbare dagen
        days_available = max(1, (due_date - start_date).days)
        
        # Basis voorspelling: dagen × gemiddelde uren per dag
        base_prediction = days_available * self.average_hours_per_day
        
        # Pas aan op basis van sleutelwoorden in titel
        multiplier = 1.0
        title_lower = title.lower()
        
        for keyword, mult in self.keyword_multipliers.items():
            if keyword in title_lower:
                multiplier = max(multiplier, mult)
        
        # Finale voorspelling
        prediction = base_prediction * multiplier
        
        # Zorg voor minimum
        return max(1.0, round(prediction, 1))

# Globale instantie
predictor = DurationPredictor()


