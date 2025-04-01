import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum, DateTime
from datetime import datetime
from sqlalchemy.orm import joinedload
from flask_cors import CORS
from dotenv import load_dotenv

env = os.getenv('FLASK_ENV', 'development')
load_dotenv(f'config/.env.{env}') 

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quickquid.db'  
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
db = SQLAlchemy(app)

print(f"Running in {os.getenv('FLASK_ENV')} mode")
print(os.getenv('ORIGINS'))

origins = os.getenv('ORIGINS', 'http://localhost:4200').split(',')

CORS(app, 
     origins=origins, 
     methods=["GET", "POST", "PUT", "DELETE"], 
     allow_headers=["Content-Type", "Authorization"],
     supports_credentials=True)


class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)

    def __init__(self, first_name, last_name):
        self.first_name = first_name
        self.last_name = last_name

class BankBranch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_name = db.Column(db.String(255), nullable=False)
    branch_name = db.Column(db.String(255), nullable=False)
    bank_address = db.Column(db.String(255), nullable=False)

    def __init__(self, bank_name, branch_name, bank_address):
        self.bank_name = bank_name
        self.branch_name = branch_name
        self.bank_address = bank_address

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(255), nullable=False)
    account_type = db.Column(Enum('SAVINGS', 'LOAN', 'CREDIT_CARD', 'CURRENT_ACCOUNT', name='account_types'), nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow)

    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('bank_branch.id'), nullable=True)

    person = db.relationship('Person', foreign_keys=[person_id], backref='accounts', passive_deletes=True)
    branch = db.relationship('BankBranch', foreign_keys=[branch_id], backref='accounts', passive_deletes=True)

    def __init__(self, account_number, account_type, currency, balance, created_at, person_id=None, branch_id=None):
        self.account_number = account_number
        self.account_type = account_type
        self.currency = currency
        self.balance = balance
        self.created_at = created_at
        self.person_id = person_id
        self.branch_id = branch_id

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(Enum('COMPLETED', 'PENDING', 'FAILED', name='transaction_status'), nullable=False)
    transaction_date = db.Column(DateTime, default=datetime.utcnow)

    sender_account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    receiver_account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    originating_branch_id = db.Column(db.Integer, db.ForeignKey('bank_branch.id'), nullable=True)

    sender = db.relationship('Account', foreign_keys=[sender_account_id], backref='sent_transactions')
    receiver = db.relationship('Account', foreign_keys=[receiver_account_id], backref='received_transactions')
    originating_branch = db.relationship('BankBranch', foreign_keys=[originating_branch_id], backref='transactions', passive_deletes=True)

    def __init__(self, amount, status, sender_account_id, receiver_account_id, description=None, transaction_date=None, originating_branch_id=None):
        self.amount = amount
        self.status = status
        self.sender_account_id = sender_account_id
        self.receiver_account_id = receiver_account_id
        self.description = description
        self.transaction_date = transaction_date or datetime.utcnow()
        self.originating_branch_id = originating_branch_id


@app.route('/person', methods=['POST'])
def create_person():

    data = request.get_json()

    if not data or not 'firstName' in data or not 'lastName' in data:
        return jsonify({"error": "Missing required fields: 'firstName' and 'lastName'"}), 400

    first_name = data['firstName']
    last_name = data['lastName']

    new_person = Person(first_name=first_name, last_name=last_name)

    try:

        db.session.add(new_person)
        db.session.commit()

        return jsonify({
            "person": {
                "id": new_person.id,
                "firstName": new_person.first_name,
                "lastName": new_person.last_name
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
@app.route('/bank', methods=['POST'])
def create_bankbranch():
    data = request.get_json()
    if not data or not all(key in data for key in ['bankName', 'branchName', 'bankAddress']):
        return jsonify({"error": "Missing required fields: 'bankName', 'branchName', and 'bankAddress'"}), 400

    bankbranch = BankBranch(
        bank_name=data['bankName'],
        branch_name=data['branchName'],
        bank_address=data['bankAddress']
    )

    try:
        db.session.add(bankbranch)
        db.session.commit()

        return jsonify({
            "bankBranch": {
                "id": bankbranch.id,
                "bankName": bankbranch.bank_name,
                "branchName": bankbranch.branch_name,
                "bankAddress": bankbranch.bank_address
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/bank/all', methods=['GET'])
def get_all_bankbranches():
    bankbranches = BankBranch.query.all()

    result = []
    for branch in bankbranches:
        result.append({
            "id": branch.id,
            "bankName": branch.bank_name,
            "branchName": branch.branch_name,
            "bankAddress": branch.bank_address
        })

    return jsonify(result), 200


@app.route('/account', methods=['POST'])
def create_account():
    data = request.get_json()

    required_fields = ['accountNumber', 'accountType', 'createdAt', 'currency', 'firstName', 'lastName', 'bankName', 'balance']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    account_number = data['accountNumber']
    account_type = data['accountType']
    created_at = data['createdAt']
    currency = data['currency']
    first_name = data['firstName']
    last_name = data['lastName']
    bank_name = data['bankName']
    balance = data['balance']

    try:
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as e:
        return jsonify({"error": f"Invalid date format: {str(e)}"}), 400

    person = Person.query.filter_by(first_name=first_name, last_name=last_name).first()
    if not person:
        return jsonify({"error": "Person not found"}), 404

    branch_id = bank_name.get('id')
    if not branch_id:
        return jsonify({"error": "Bank branch ID not found in bankName"}), 404

    account = Account(
        account_number=account_number,
        account_type=account_type,
        currency=currency,
        balance=balance,
        created_at=created_at,
        person_id=person.id,
        branch_id=branch_id
    )

    try:
        db.session.add(account)
        db.session.commit()

        return jsonify({
            "account": {
                "id": account.id,
                "accountNumber": account.account_number,
                "accountType": account.account_type,
                "createdAt": account.created_at.strftime('%Y-%m-%dT%H:%M:%S'),
                "currency": account.currency,
                "balance": account.balance,
                "firstName": person.first_name,
                "lastName": person.last_name,
                "bankName": bank_name.get('name')
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    
@app.route('/transaction', methods=['POST'])
def create_transaction():
    try:
        data = request.get_json()
        amount = data.get('amount')
        description = data.get('description')
        sender_account_number = data.get('senderAccount')
        receiver_account_number = data.get('receiverAccount')
        originating_branch_id = data.get('originatingBranch')

        if not all([amount, sender_account_number, receiver_account_number]):
            return jsonify({"message": "Missing required fields"}), 400

        sender = Account.query.filter_by(account_number=sender_account_number).first()
        if not sender:
            return jsonify({"message": "Sender account not found"}), 400

        receiver = Account.query.filter_by(account_number=receiver_account_number).first()
        if not receiver:
            return jsonify({"message": "Receiver account not found"}), 400

        if sender.balance < amount:
            status = "FAILED"
        else:
            status = "COMPLETED"
            sender.balance -= amount
            receiver.balance += amount
            db.session.add(receiver)
            db.session.add(sender)


        originating_branch_id = originating_branch_id.get('id') if originating_branch_id else None
        if not originating_branch_id:
            return jsonify({"error": "Bank branch ID not found in bankName"}), 404
        
        transaction = Transaction(
            amount=amount,
            description=description,
            status=status,
            sender_account_id=sender.id,
            receiver_account_id=receiver.id,
            originating_branch_id=originating_branch_id,
            transaction_date=datetime.utcnow()
        )

        db.session.add(transaction) 
        db.session.commit()

        return jsonify({
            "id": transaction.id,
            "amount": transaction.amount,
            "description": transaction.description,
            "status": transaction.status,
            "transaction_date": transaction.transaction_date.strftime('%Y-%m-%dT%H:%M:%S'),
            "sender_account_id": transaction.sender_account_id,
            "receiver_account_id": transaction.receiver_account_id,
            "originating_branch_id": transaction.originating_branch_id
        }), 201

    except Exception as e:
        print(e)
        return jsonify({"message": "Internal Server Error"}), 500

    
@app.route('/transaction/account', methods=['GET'])
def get_transactions_by_account():
    try:
        account_number = request.args.get('accountNumber')
        
        if not account_number:
            return jsonify({"message": "Account number is required"}), 400
        
        sender_account = Account.query.filter_by(account_number=account_number).first()
        if not sender_account:
            return jsonify({"message": "Account not found"}), 404
        
        transactions = Transaction.query.filter(
            (Transaction.sender_account_id == sender_account.id) |
            (Transaction.receiver_account_id == sender_account.id)
        ).options(
            joinedload(Transaction.sender).joinedload(Account.person),
            joinedload(Transaction.receiver).joinedload(Account.person),
            joinedload(Transaction.originating_branch)
        ).all()

        formatted_transactions = []
        for transaction in transactions:
            formatted_transactions.append({
                "amount": transaction.amount,
                "sender": f"{transaction.sender.person.first_name} {transaction.sender.person.last_name}",
                "receiver": f"{transaction.receiver.person.first_name} {transaction.receiver.person.last_name}",
                "bank": f"{transaction.originating_branch.bank_name} - {transaction.originating_branch.branch_name}" if transaction.originating_branch else None,
                "date": transaction.transaction_date.strftime('%Y-%m-%dT%H:%M:%S'),
                "description": transaction.description,
                "status": transaction.status
            })
        
        return jsonify(formatted_transactions), 200
    
    except Exception as e:
        print(e)
        return jsonify({"message": "Error retrieving transactions"}), 500

with app.app_context():
    db.drop_all()
    db.create_all()

if __name__ == '__main__':
    app.run(debug=os.getenv('DEBUG'), port=8080)
