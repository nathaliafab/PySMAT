class DiscountCalculator:
    def __init__(self, discount=-5):
        self.discount = discount  # variável de instância

    def apply(self, price):
        if price > 50:
            self.discount = -10  # aplica desconto condicionalmente
        
        final_price = price + self.discount
        return final_price