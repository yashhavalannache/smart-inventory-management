from flask import Flask, render_template, request, redirect, url_for, session, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO



app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///store.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), unique=True, nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    cost_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    profit = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

class Sales(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)

# Routes
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('home'))
        else:
            return "Invalid credentials"
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            return "Email already registered"
        new_user = User(email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    items = Inventory.query.order_by(Inventory.product_id.asc()).all()  # Order by product_id ascending
    message = None

    if request.method == 'POST':
        action = request.form.get('action')

        if action == "Add":
            product_id = request.form['product_id']
            product_name = request.form['product_name']
            cost_price = float(request.form['cost_price'])
            selling_price = float(request.form['selling_price'])
            quantity = int(request.form['quantity'])
            profit = selling_price - cost_price

            if Inventory.query.filter_by(product_id=product_id).first():
                message = "Product ID already exists!"
            else:
                new_item = Inventory(
                    product_id=product_id,
                    product_name=product_name,
                    cost_price=cost_price,
                    selling_price=selling_price,
                    profit=profit,
                    quantity=quantity
                )
                db.session.add(new_item)
                db.session.commit()
                return redirect(url_for('inventory'))

        elif action == "Delete":
            product_id = request.form['product_id']
            item_to_delete = Inventory.query.filter_by(product_id=product_id).first()
            if item_to_delete:
                db.session.delete(item_to_delete)
                db.session.commit()
                return redirect(url_for('inventory'))

        elif action == "Update":
            product_id = request.form['product_id']
            new_quantity = int(request.form['new_quantity'])
            item_to_update = Inventory.query.filter_by(product_id=product_id).first()
            if item_to_update:
                item_to_update.quantity = new_quantity
                db.session.commit()
                return redirect(url_for('inventory'))
            else:
                message = "Product ID not found!"

    return render_template('inventory.html', items=items, message=message)



@app.route('/sales', methods=['GET', 'POST'])
def sales():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    sales_data = []
    error = None

    if request.method == 'POST':
        date = request.form.get('date')  # Get the selected date
        if not date:
            error = "Please select a valid date."
        else:
            try:
                sales_data = Sales.query.filter(Sales.date == date).all()  # Fetch sales for the selected date
                if not sales_data:
                    error = f"No sales records found for {date}."
            except Exception as e:
                error = f"An error occurred while fetching sales: {str(e)}"

    return render_template('sales.html', sales=sales_data, error=error)



@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    items = Inventory.query.all()  # Fetch all inventory items
    sales_result = []

    if request.method == 'POST':
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')

        try:
            for product_id, quantity in zip(product_ids, quantities):
                quantity = int(quantity)
                if quantity <= 0:
                    return "Quantity must be greater than zero."

                product = Inventory.query.filter_by(product_id=product_id).first()
                if not product:
                    return f"Product with ID {product_id} not found."
                if product.quantity < quantity:
                    return f"Insufficient stock for {product.product_name}. Available: {product.quantity}."

                # Update inventory and record sale
                total_price = product.selling_price * quantity
                product.quantity -= quantity  # Reduce the quantity in inventory
                db.session.commit()  # Commit the inventory change

                # Record the sale in Sales table
                sale = Sales(
                    product_id=product_id,
                    product_name=product.product_name,
                    quantity=quantity,
                    total_price=total_price,
                    date=datetime.now().date()  # Record current date
                )
                db.session.add(sale)
                sales_result.append({
                    'product_name': product.product_name,
                    'quantity': quantity,
                    'total_price': total_price
                })

            db.session.commit()  # Commit all sales data
        except Exception as e:
            db.session.rollback()  # Rollback in case of an error
            return f"An error occurred: {str(e)}"

    return render_template('sell.html', items=items, sales_result=sales_result)


@app.route('/dashboard')
def dashboard():
    # Redirect if not logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Fetch total sales and profit for today
    total_sales = db.session.query(func.sum(Sales.total_price)).filter(Sales.date == func.current_date()).scalar() or 0
    total_profit = db.session.query(func.sum(Inventory.profit)).filter(Sales.date == func.current_date()).scalar() or 0

    # Fetch top 5 most sold items
    top_sold_items = (
        db.session.query(Sales.product_name, func.sum(Sales.quantity).label('total_quantity'))
        .filter(Sales.date == func.current_date())
        .group_by(Sales.product_name)
        .order_by(func.sum(Sales.quantity).desc())
        .limit(5)
        .all()
    )

    # Fetch low stock items
    low_stock = db.session.query(Inventory.product_name, Inventory.quantity).filter(Inventory.quantity < 5).all()

    # Fetch top 5 profitable products
    top_profit_products = (
        db.session.query(Inventory.product_name, func.sum(Inventory.profit).label('total_profit'))
        .join(Sales, Inventory.product_id == Sales.product_id)
        .filter(Sales.date == func.current_date())
        .group_by(Inventory.product_name)
        .order_by(func.sum(Inventory.profit).desc())
        .limit(5)
        .all()
    )

    return render_template(
        'dashboard.html',
        total_sales=total_sales,
        total_profit=total_profit,
        top_sold_items=top_sold_items,
        low_stock=low_stock,
        top_profit_products=top_profit_products,
    )


@app.route('/report', methods=['GET', 'POST'])
def report():
    if request.method == 'POST':
        report_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()

        total_items_sold = db.session.query(db.func.sum(Sales.quantity)).filter(Sales.date == report_date).scalar() or 0
        total_profit = db.session.query(db.func.sum(Sales.quantity * Inventory.profit)) \
            .join(Inventory, Sales.product_id == Inventory.product_id) \
            .filter(Sales.date == report_date).scalar() or 0

        top_selling = db.session.query(
            Sales.product_name,
            db.func.sum(Sales.quantity).label('total_quantity')
        ).filter(Sales.date == report_date).group_by(Sales.product_name).order_by(db.desc('total_quantity')).limit(5).all()

        least_selling = db.session.query(
            Sales.product_name,
            db.func.sum(Sales.quantity).label('total_quantity')
        ).filter(Sales.date == report_date).group_by(Sales.product_name).order_by('total_quantity').limit(5).all()

        top_performance = db.session.query(
            Inventory.product_name,
            db.func.sum(Sales.quantity).label('units_sold'),
            db.func.sum(Sales.total_price).label('revenue'),
            (db.func.sum(Sales.quantity * Inventory.profit) / db.func.sum(Sales.total_price) * 100).label('profit_margin')
        ).join(Sales, Inventory.product_id == Sales.product_id) \
            .filter(Sales.date == report_date) \
            .group_by(Inventory.product_name) \
            .order_by(db.desc('units_sold')).limit(5).all()

        if request.form.get('action') == 'View':
            return render_template(
                'report.html',
                report_date=report_date,
                total_items_sold=total_items_sold,
                total_profit=total_profit,
                top_selling=top_selling,
                least_selling=least_selling,
                top_performance=top_performance
            )

        elif request.form.get('action') == 'Download PDF':
            response = make_response(generate_pdf(report_date, total_items_sold, total_profit, top_selling, least_selling, top_performance))
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = 'inline; filename=report.pdf'
            return response

    return render_template('report_form.html')



def generate_pdf(report_date, total_items_sold, total_profit, top_selling, least_selling, top_performance):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    # Heading
    c.setFont("Helvetica-Bold", 16)
    c.drawString(200, 750, "SMART STORE DAILY REPORT")

    # Report Date
    c.setFont("Helvetica", 12)
    c.drawString(200, 730, f"Report for: {report_date}")

    # Summary
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, 700, "Summary")
    c.setFont("Helvetica", 12)
    c.drawString(100, 680, f"Total Items Sold: {total_items_sold}")
    c.drawString(100, 660, f"Total Profit: Rs.{total_profit}")

    # Top Selling Items
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, 620, "Top Selling Products:")
    y = 600
    c.setFont("Helvetica", 12)
    for item in top_selling:
        c.drawString(100, y, f"{item[0]}: {item[1]} units sold")
        y -= 20

    # Least Selling Items
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y-20, "Least Selling Products:")
    y -= 40
    c.setFont("Helvetica", 12)
    for item in least_selling:
        c.drawString(100, y, f"{item[0]}: {item[1]} units sold")
        y -= 20

    # Top Performance Products
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y-20, "Top Performance Products:")
    y -= 40
    c.setFont("Helvetica", 12)
    for item in top_performance:
        c.drawString(100, y, f"{item[0]}: {item[1]} units sold, Rs.{item[2]} revenue")
        y -= 20

    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


if __name__ == '__main__':
    try:
        with app.app_context():
            db.create_all()
        app.run(debug=True)
    except Exception as e:
        print(f"Error: {str(e)}")

