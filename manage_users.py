#!/usr/bin/env python3
import argparse
import getpass
import sys

from werkzeug.security import generate_password_hash

from app import app
from models import User, db


def cmd_list():
    with app.app_context():
        users = User.query.order_by(User.id).all()
        if not users:
            print('Keine Benutzer vorhanden.')
            return
        print(f'{"ID":<5} {"Benutzername":<20} {"Admin":<8} {"Erstellt"}')
        print('-' * 60)
        for u in users:
            admin = 'Ja' if u.is_admin else 'Nein'
            created = u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else '-'
            print(f'{u.id:<5} {u.username:<20} {admin:<8} {created}')


def cmd_create(username):
    with app.app_context():
        if User.query.filter_by(username=username).first():
            print(f'Fehler: Benutzer „{username}" existiert bereits.')
            sys.exit(1)
        password = getpass.getpass('Passwort: ')
        if len(password) < 4:
            print('Fehler: Passwort muss mindestens 4 Zeichen lang sein.')
            sys.exit(1)
        confirm = getpass.getpass('Passwort bestätigen: ')
        if password != confirm:
            print('Fehler: Passwörter stimmen nicht überein.')
            sys.exit(1)
        user = User(username=username,
                     password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        print(f'Benutzer „{username}" erstellt.')


def cmd_reset_password(username):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f'Fehler: Benutzer „{username}" nicht gefunden.')
            sys.exit(1)
        password = getpass.getpass('Neues Passwort: ')
        if len(password) < 4:
            print('Fehler: Passwort muss mindestens 4 Zeichen lang sein.')
            sys.exit(1)
        confirm = getpass.getpass('Passwort bestätigen: ')
        if password != confirm:
            print('Fehler: Passwörter stimmen nicht überein.')
            sys.exit(1)
        user.password_hash = generate_password_hash(password)
        db.session.commit()
        print(f'Passwort für „{username}" zurückgesetzt.')


def main():
    parser = argparse.ArgumentParser(description='PrintCostCalc Benutzerverwaltung')
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('list', help='Alle Benutzer auflisten')

    p_create = sub.add_parser('create', help='Neuen Benutzer erstellen')
    p_create.add_argument('username', help='Benutzername')

    p_reset = sub.add_parser('reset-password', help='Passwort zurücksetzen')
    p_reset.add_argument('username', help='Benutzername')

    args = parser.parse_args()
    if args.command == 'list':
        cmd_list()
    elif args.command == 'create':
        cmd_create(args.username)
    elif args.command == 'reset-password':
        cmd_reset_password(args.username)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
