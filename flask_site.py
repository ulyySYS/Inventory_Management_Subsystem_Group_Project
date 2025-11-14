from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from markupsafe import escape
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'

db = SQLAlchemy(app)

# Make datetime available in templates
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

class Product(db.Model):
    __tablename__ = 'product'

    productID = db.Column(db.Integer, primary_key=True)
    productName = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)
    unitMeasure = db.Column(db.Float, nullable=False)

    def getProductInfo(self):
        """Get product information as a string"""
        return f"{self.productName} ({self.category}) - ${self.price}"
    
    def updatePrice(self, newPrice):
        """Update product price"""
        self.price = newPrice


class Inventory(db.Model):
    __tablename__ = 'inventory'

    SKU = db.Column(db.Integer, primary_key=True)
    productID = db.Column(db.Integer, db.ForeignKey('product.productID'), nullable=False)
    quantityOnHand = db.Column(db.Float, nullable=False)
    isLowStock = db.Column(db.Boolean, default=False)
    inventoryCost = db.Column(db.Float, nullable=False)
    unitMeasure = db.Column(db.Float, nullable=False)

    product = db.relationship('Product', backref='inventory_items')

    def updateStock(self, quantity_int):
        """Update stock quantity"""
        self.quantityOnHand = quantity_int


class OrderItem(db.Model):
    __tablename__ = 'orderitem'

    orderItemID = db.Column(db.Integer, primary_key=True)
    orderID = db.Column(db.Integer, nullable=False)
    productID = db.Column(db.Integer, db.ForeignKey('product.productID'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    product = db.relationship('Product', backref='order_items')

    def calculateSubtotal(self):
        """Calculate subtotal based on quantity and product price"""
        if self.product:
            self.subtotal = self.quantity * self.product.price
            return self.subtotal
        return 0.0
    
    def updatePrice(self, newPrice):
        """Update price and recalculate subtotal"""
        if self.product:
            self.product.price = newPrice
            self.calculateSubtotal()


with app.app_context():
    db.create_all()


# LOW STOCK THRESHOLD
LOW_STOCK_THRESHOLD = 10


def check_low_stock():
    """Check all inventory items and update isLowStock status"""
    inventory_items = Inventory.query.all()
    for item in inventory_items:
        if item.quantityOnHand <= LOW_STOCK_THRESHOLD:
            item.isLowStock = True
        else:
            item.isLowStock = False
    db.session.commit()


def get_low_stock_items():
    """Get all items that are low in stock"""
    return Inventory.query.filter(Inventory.isLowStock == True).all()



# CODE FOR ADD INVENTORY ITEM 
@app.route('/inventory/add', methods=['GET', 'POST'])
def add_inventory():
    """Add inventory item - creates new product and inventory entry together"""
    if request.method == 'POST':
        try:
            # Create the Product first
            product_name = request.form.get('productName')
            category = request.form.get('category')
            price = float(request.form.get('price'))
            product_unit_measure = float(request.form.get('productUnitMeasure'))
            
            new_product = Product(
                productName=product_name,
                category=category,
                price=price,
                unitMeasure=product_unit_measure
            )
            
            db.session.add(new_product)
            db.session.flush()  
            
            
            quantity = float(request.form.get('quantityOnHand'))
            inventory_cost = float(request.form.get('inventoryCost'))
            inventory_unit_measure = float(request.form.get('inventoryUnitMeasure'))
            
            new_inventory = Inventory(
                productID=new_product.productID,
                quantityOnHand=quantity,
                inventoryCost=inventory_cost,
                unitMeasure=inventory_unit_measure,
                isLowStock=False
            )
            
            db.session.add(new_inventory)
            db.session.commit()
            
            flash(f'Product "{product_name}" added to inventory successfully!', 'success')
            return redirect(url_for('index'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding product: {str(e)}', 'error')
            return redirect(url_for('add_inventory'))
    

    return render_template('add_inventory.html')


# CODE FOR UPDATING STOCK QUANTITY
@app.route('/inventory/update-quantity/<int:sku>', methods=['GET', 'POST'])
def update_quantity(sku):
    """Update quantity on hand for an inventory item"""
    inventory_item = Inventory.query.get_or_404(sku)
    product = Product.query.get(inventory_item.productID)
    
    if request.method == 'POST':
        new_quantity = float(request.form.get('quantityOnHand'))
        inventory_item.quantityOnHand = new_quantity
        
        # Check if it's low stock
        if new_quantity <= LOW_STOCK_THRESHOLD:
            inventory_item.isLowStock = True
        else:
            inventory_item.isLowStock = False
            
        db.session.commit()
        
        flash(f'Quantity updated successfully for "{product.productName}"!', 'success')
        return redirect(url_for('index'))
    
    return render_template('update_quantity.html', inventory=inventory_item, product=product)


# CODE FOR UPDATING INVENTORY ITEM DETAILS
@app.route('/inventory/update/<int:sku>', methods=['GET', 'POST'])
def update_inventory_item(sku):
    """Update product and inventory details"""
    inventory_item = Inventory.query.get_or_404(sku)
    product = Product.query.get(inventory_item.productID)
    
    if request.method == 'POST':
        # Update Product details
        product.productName = request.form.get('productName')
        product.category = request.form.get('category')
        product.price = float(request.form.get('price'))
        product.unitMeasure = float(request.form.get('productUnitMeasure'))
        
        # Update Inventory details
        inventory_item.inventoryCost = float(request.form.get('inventoryCost'))
        inventory_item.unitMeasure = float(request.form.get('inventoryUnitMeasure'))
        
        db.session.commit()
        
        flash(f'"{product.productName}" updated successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('update_inventory.html', inventory=inventory_item, product=product)


# CODE FOR GENERATING INVENTORY REPORT
@app.route('/inventory/report')
def inventory_report():
    """Generate comprehensive inventory report"""
    check_low_stock()  # Update low stock status first
    
    inventory_items = db.session.query(Inventory, Product).join(
        Product, Inventory.productID == Product.productID
    ).all()
    
    # Calculate report statistics
    total_items = len(inventory_items)
    total_inventory_value = sum(inv.quantityOnHand * inv.inventoryCost for inv, prod in inventory_items)
    low_stock_items = [item for item in inventory_items if item[0].isLowStock]
    low_stock_count = len(low_stock_items)
    
    # Category breakdown
    categories = {}
    for inv, prod in inventory_items:
        if prod.category not in categories:
            categories[prod.category] = {
                'count': 0,
                'total_value': 0,
                'total_quantity': 0
            }
        categories[prod.category]['count'] += 1
        categories[prod.category]['total_value'] += inv.quantityOnHand * inv.inventoryCost
        categories[prod.category]['total_quantity'] += inv.quantityOnHand
    
    return render_template('inventory_report.html', 
                         inventory_items=inventory_items,
                         total_items=total_items,
                         total_inventory_value=total_inventory_value,
                         low_stock_items=low_stock_items,
                         low_stock_count=low_stock_count,
                         categories=categories)


# THIS IS ALSO THE VIEW INVENTORY, SINCE THE INVENTORY ITEMS ARE DISPLAYED ON START OF THE PAGE
# HOME PAGE
@app.route('/') 
@app.route('/home') 
def index(user_name=None):
    """Home page showing inventory table"""
    check_low_stock()  # Check and update low stock status
    
    inventory_items = db.session.query(Inventory, Product).join(
        Product, Inventory.productID == Product.productID
    ).all()
    
    # Get low stock items for notification
    low_stock_items = get_low_stock_items()
    low_stock_count = len(low_stock_items)
    
    return render_template('home.html', user=user_name, inventory_items=inventory_items, 
                         low_stock_count=low_stock_count, low_stock_items=low_stock_items)


if __name__ == '__main__':
    app.run(debug=True)
