class DiscountCalculator:
    def __init__(self, discount=-5):
        self.discount = discount  # variável de instância
    
    def apply(self, price):
        final_price = price + self.discount
        return final_price