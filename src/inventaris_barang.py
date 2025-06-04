import tkinter as tk
from tkinter import ttk, messagebox, filedialog, PhotoImage
from tkinter.ttk import Notebook
import sqlite3
import os
import json
from datetime import datetime, timedelta
from fpdf import FPDF
import barcode
from barcode.writer import ImageWriter
import tempfile
from PIL import Image, ImageTk
from tkcalendar import DateEntry
import logging

class DatabaseHandler:
    def __init__(self):
        self.db_name = "inventaris.db"
        self.initialize_database()

    def initialize_database(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Create items table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            barcode TEXT UNIQUE,
            quantity INTEGER NOT NULL,
            location TEXT,
            condition TEXT,
            status TEXT,
            photo_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create transactions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            borrower TEXT NOT NULL,
            purpose TEXT,
            date TEXT NOT NULL,
            due_date TEXT,
            returned INTEGER DEFAULT 0,
            quantity INTEGER DEFAULT 1,
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
        ''')

        conn.commit()
        conn.close()

    def add_item(self, item_data):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO items (name, barcode, quantity, location, condition, status, photo_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                item_data['name'],
                item_data['barcode'],
                item_data['quantity'],
                item_data['location'],
                item_data['condition'],
                item_data['status'],
                item_data['photo_path']
            ))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return None
        finally:
            conn.close()
    
    def update_item(self, item_id, item_data):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            UPDATE items 
            SET name=?, quantity=?, location=?, condition=?, status=?, photo_path=?
            WHERE id=?
            ''', (
                item_data['name'],
                item_data['quantity'],
                item_data['location'],
                item_data['condition'],
                item_data['status'],
                item_data['photo_path'],
                item_id
            ))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return False
        finally:
            conn.close()
    
    def delete_item(self, item_id):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM items WHERE id=?', (item_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return False
        finally:
            conn.close()
    
    def get_item(self, item_id):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM items WHERE id=?', (item_id,))
            return cursor.fetchone()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return None
        finally:
            conn.close()
    
    def search_items(self, search_term):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT * FROM items 
            WHERE name LIKE ? OR barcode LIKE ?
            ''', (f'%{search_term}%', f'%{search_term}%'))
            return cursor.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return []
        finally:
            conn.close()
    
    def get_all_items(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM items')
            return cursor.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return []
        finally:
            conn.close()
    
    def add_transaction(self, transaction_data):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            # Add transaction to table
            cursor.execute('''
                INSERT INTO transactions (item_id, type, borrower, purpose, date, due_date, quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                transaction_data['item_id'],
                transaction_data['type'],
                transaction_data['borrower'],
                transaction_data['purpose'],
                transaction_data['date'],
                transaction_data['due_date'],
                transaction_data.get('quantity', 1)
            ))
            
            # Update item stock
            quantity = transaction_data.get('quantity', 1)
            item_id = transaction_data['item_id']

            if transaction_data['type'] == 'borrow':
                cursor.execute('''
                    UPDATE items SET quantity = quantity - ? WHERE id = ?
                ''', (quantity, item_id))
            elif transaction_data['type'] == 'return':
                cursor.execute('''
                    UPDATE items SET quantity = quantity + ? WHERE id = ?
                ''', (quantity, item_id))
            
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            conn.rollback()
            messagebox.showerror("Database Error", str(e))
            return None
        finally:
            conn.close()
    
    def get_transactions(self, item_id=None):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            if item_id:
                cursor.execute('''
                SELECT t.*, i.name 
                FROM transactions t
                JOIN items i ON t.item_id = i.id
                WHERE t.item_id = ?
                ORDER BY t.date DESC
                ''', (item_id,))
            else:
                cursor.execute('''
                SELECT t.*, i.name 
                FROM transactions t
                JOIN items i ON t.item_id = i.id
                ORDER BY t.date DESC
                ''')
            return cursor.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return []
        finally:
            conn.close()
    
    def get_overdue_transactions(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('''
            SELECT t.*, i.name 
            FROM transactions t
            JOIN items i ON t.item_id = i.id
            WHERE t.type = 'borrow' AND t.returned = 0 AND t.due_date < ?
            ''', (today,))
            return cursor.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", str(e))
            return []
        finally:
            conn.close()

class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.db_name = "inventaris.db"  # <-- TAMBAHKAN INI
        self.root.title("Manajemen Inventaris Barang Sekolah")
        self.root.geometry("1000x700")
        
        self.db = DatabaseHandler()
        self.current_item_id = None
        self.photo_path = None
        self.photo_preview = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # Modern Style Configuration
        style = ttk.Style()
        
        # Gunakan tema 'clam' sebagai base yang lebih modern
        style.theme_use('clam')
        
        # Color Palette Professional
        self.colors = {
            'primary': '#4a6fa5',
            'primary_dark': '#3a5a80',
            'secondary': '#6c757d',
            'success': '#28a745',
            'danger': '#dc3545',
            'light': '#f8f9fa',
            'dark': '#343a40',
            'background': '#f5f5f7',
            'card': '#ffffff'
        }
        
        # Configure Styles
        style.configure('.', 
                      background=self.colors['background'],
                      foreground=self.colors['dark'],
                      font=('Segoe UI', 10))
        
        style.configure('TFrame',
                      background=self.colors['card'],
                      borderwidth=0,
                      relief='flat')
        
        style.configure('TLabel',
                      background=self.colors['card'],
                      foreground=self.colors['dark'],
                      font=('Segoe UI', 10))
        
        style.configure('TButton',
                      background=self.colors['primary'],
                      foreground='white',
                      font=('Segoe UI', 10, 'bold'),
                      borderwidth=0,
                      relief='flat',
                      padding=8)
        
        style.map('TButton',
                background=[('active', self.colors['primary_dark']),
                          ('disabled', '#cccccc')],
                foreground=[('disabled', '#888888')])
        
        style.configure('TEntry',
                      fieldbackground='white',
                      foreground=self.colors['dark'],
                      bordercolor=self.colors['secondary'],
                      lightcolor=self.colors['secondary'],
                      darkcolor=self.colors['secondary'],
                      insertcolor=self.colors['dark'],
                      font=('Segoe UI', 10),
                      padding=6)
        
        style.configure('TCombobox',
                      fieldbackground='white',
                      foreground=self.colors['dark'],
                      selectbackground=self.colors['primary'],
                      selectforeground='white',
                      font=('Segoe UI', 10),
                      padding=6)
        
        style.configure('Treeview',
                      background='white',
                      foreground=self.colors['dark'],
                      fieldbackground='white',
                      borderwidth=0,
                      font=('Segoe UI', 9))
        
        style.configure('Treeview.Heading',
                      background=self.colors['primary'],
                      foreground='white',
                      font=('Segoe UI', 10, 'bold'),
                      padding=8,
                      borderwidth=0)
        
        style.map('Treeview',
                 background=[('selected', self.colors['primary'])],
                 foreground=[('selected', 'white')])
        
        # Main container with subtle shadow effect
        self.main_container = ttk.Frame(self.root, style='TFrame')
        self.main_container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Modern Notebook with minimal styling
        self.notebook = Notebook(self.main_container, style='TNotebook')
        self.notebook.pack(fill='both', expand=True)
        
        # Configure Notebook Style
        style.configure('TNotebook',
                      background=self.colors['background'],
                      borderwidth=0)
        
        style.configure('TNotebook.Tab',
                      background=self.colors['background'],
                      foreground=self.colors['dark'],
                      font=('Segoe UI', 10, 'bold'),
                      padding=(12, 6),
                      borderwidth=0)
        
        style.map('TNotebook.Tab',
                background=[('selected', self.colors['card']),
                          ('active', self.colors['light'])],
                foreground=[('selected', self.colors['primary']),
                          ('active', self.colors['primary'])])
        
        # Create tabs with icons (using emoji for simplicity)
        self.create_input_tab()
        self.create_search_tab()
        self.create_transaction_tab()
        self.create_import_export_tab()
        
        # Status bar
        self.status_bar = ttk.Frame(self.main_container,
                                  style='TFrame',
                                  height=24)
        self.status_bar.pack(fill='x', pady=(10, 0))
        
        self.status_label = ttk.Label(self.status_bar,
                                    text="Sistem Manajemen Inventaris Sekolah",
                                    style='TLabel')
        self.status_label.pack(side='left', padx=10)
        
        # Check for overdue transactions
        self.check_overdue_transactions()
        
        # Set focus to first field
        self.root.after(100, lambda: self.name_entry.focus_set())
    
    def create_input_tab(self):
        # Input Tab
        input_tab = ttk.Frame(self.notebook)
        self.notebook.add(input_tab, text="Input Barang")
        
        # Main frame with padding
        main_frame = ttk.Frame(input_tab)
        main_frame.pack(padx=20, pady=20, fill='both', expand=True)
        
        # Form frame
        form_frame = ttk.Frame(main_frame)
        form_frame.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        
        # Item details
        ttk.Label(form_frame, text="Nama Barang:").grid(row=0, column=0, sticky='w', pady=5)
        self.name_entry = ttk.Entry(form_frame, width=40)
        self.name_entry.grid(row=0, column=1, sticky='w', pady=5)
        
        ttk.Label(form_frame, text="Jumlah:").grid(row=1, column=0, sticky='w', pady=5)
        self.quantity_entry = ttk.Entry(form_frame, width=10)
        self.quantity_entry.grid(row=1, column=1, sticky='w', pady=5)
        
        ttk.Label(form_frame, text="Lokasi:").grid(row=2, column=0, sticky='w', pady=5)
        self.location_entry = ttk.Entry(form_frame, width=40)
        self.location_entry.grid(row=2, column=1, sticky='w', pady=5)
        
        ttk.Label(form_frame, text="Kondisi:").grid(row=3, column=0, sticky='w', pady=5)
        self.condition_combobox = ttk.Combobox(form_frame, values=["Baik", "Rusak Ringan", "Rusak Berat"], width=15)
        self.condition_combobox.grid(row=3, column=1, sticky='w', pady=5)
        self.condition_combobox.set("Baik")
        
        ttk.Label(form_frame, text="Status:").grid(row=4, column=0, sticky='w', pady=5)
        self.status_combobox = ttk.Combobox(form_frame, values=["Tersedia", "Dipinjam", "Perbaikan"], width=15)
        self.status_combobox.grid(row=4, column=1, sticky='w', pady=5)
        self.status_combobox.set("Tersedia")
        
        # Barcode section
        ttk.Label(form_frame, text="Barcode:").grid(row=5, column=0, sticky='w', pady=5)
        self.barcode_label = ttk.Label(form_frame, text="(Akan digenerate otomatis)")
        self.barcode_label.grid(row=5, column=1, sticky='w', pady=5)
        
        # Photo section
        ttk.Label(form_frame, text="Foto Barang:").grid(row=6, column=0, sticky='w', pady=5)
        self.photo_button = ttk.Button(form_frame, text="Pilih Foto", command=self.upload_photo)
        self.photo_button.grid(row=6, column=1, sticky='w', pady=5)
        
        self.photo_preview_label = ttk.Label(form_frame)
        self.photo_preview_label.grid(row=7, column=1, sticky='w', pady=5)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, sticky='e', pady=10)
        
        self.save_button = ttk.Button(button_frame, text="Simpan", command=self.save_item)
        self.save_button.pack(side='left', padx=5)
        
        self.update_button = ttk.Button(button_frame, text="Update", command=self.update_item, state='disabled')
        self.update_button.pack(side='left', padx=5)
        
        self.clear_button = ttk.Button(button_frame, text="Clear", command=self.clear_form)
        self.clear_button.pack(side='left', padx=5)
        
        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
    
    def create_search_tab(self):
        # Search Tab
        search_tab = ttk.Frame(self.notebook)
        self.notebook.add(search_tab, text="Cari Barang")
        
        # Search frame
        search_frame = ttk.Frame(search_tab)
        search_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(search_frame, text="Cari:").pack(side='left', padx=5)
        self.search_entry = ttk.Entry(search_frame, width=40)
        self.search_entry.pack(side='left', padx=5)
        
        search_button = ttk.Button(search_frame, text="Cari", command=self.search_items)
        search_button.pack(side='left', padx=5)
        
        show_all_button = ttk.Button(search_frame, text="Tampilkan Semua", command=self.show_all_items)
        show_all_button.pack(side='left', padx=5)
        
        # Results frame
        results_frame = ttk.Frame(search_tab)
        results_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Treeview for results
        columns = ('id', 'name', 'quantity', 'location', 'condition', 'status')
        self.results_tree = ttk.Treeview(
            results_frame, 
            columns=columns, 
            show='headings',
            selectmode='browse'
        )
        
        # Configure columns
        self.results_tree.heading('id', text='ID')
        self.results_tree.column('id', width=50, anchor='center')
        
        self.results_tree.heading('name', text='Nama Barang')
        self.results_tree.column('name', width=200)
        
        self.results_tree.heading('quantity', text='Jumlah')
        self.results_tree.column('quantity', width=80, anchor='center')
        
        self.results_tree.heading('location', text='Lokasi')
        self.results_tree.column('location', width=150)
        
        self.results_tree.heading('condition', text='Kondisi')
        self.results_tree.column('condition', width=120)
        
        self.results_tree.heading('status', text='Status')
        self.results_tree.column('status', width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.results_tree.pack(fill='both', expand=True)
        
        # Action buttons frame
        action_frame = ttk.Frame(search_tab)
        action_frame.pack(fill='x', padx=10, pady=10)
        
        view_button = ttk.Button(action_frame, text="Lihat Detail", command=self.view_item_details)
        view_button.pack(side='left', padx=5)
        
        edit_button = ttk.Button(action_frame, text="Edit", command=self.edit_selected_item)
        edit_button.pack(side='left', padx=5)
        
        delete_button = ttk.Button(action_frame, text="Hapus", command=self.delete_selected_item)
        delete_button.pack(side='left', padx=5)
        
        # Bind double click to view details
        self.results_tree.bind('<Double-1>', lambda e: self.view_item_details())
    
    def create_transaction_tab(self):
        # Transaction Tab
        transaction_tab = ttk.Frame(self.notebook)
        self.notebook.add(transaction_tab, text="Transaksi")
        
        # Main frame with notebook
        trans_notebook = Notebook(transaction_tab)
        trans_notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Borrow frame
        borrow_frame = ttk.Frame(trans_notebook)
        trans_notebook.add(borrow_frame, text="Peminjaman")
        
        # Return frame
        return_frame = ttk.Frame(trans_notebook)
        trans_notebook.add(return_frame, text="Pengembalian")
        
        # History frame
        history_frame = ttk.Frame(trans_notebook)
        trans_notebook.add(history_frame, text="Riwayat")
        
        # Configure borrow frame
        self.setup_borrow_frame(borrow_frame)
        self.setup_return_frame(return_frame)
        self.setup_history_frame(history_frame)
    
    def setup_borrow_frame(self, frame):
        # Item selection
        ttk.Label(frame, text="Barang:").grid(row=0, column=0, sticky='w', pady=5, padx=10)
        
        self.borrow_item_combobox = ttk.Combobox(frame, state='readonly')
        self.borrow_item_combobox.grid(row=0, column=1, sticky='we', pady=5, padx=10)
        
        # Borrower info
        ttk.Label(frame, text="Peminjam:").grid(row=1, column=0, sticky='w', pady=5, padx=10)
        self.borrower_entry = ttk.Entry(frame)
        self.borrower_entry.grid(row=1, column=1, sticky='we', pady=5, padx=10)
        
        # Purpose
        ttk.Label(frame, text="Tujuan:").grid(row=2, column=0, sticky='w', pady=5, padx=10)
        self.purpose_entry = ttk.Entry(frame)
        self.purpose_entry.grid(row=2, column=1, sticky='we', pady=5, padx=10)
        
        # Due date - menggunakan DateEntry
        ttk.Label(frame, text="Tanggal Kembali:").grid(row=3, column=0, sticky='w', pady=5, padx=10)
        self.due_date_entry = DateEntry(
            frame,
            date_pattern='dd/mm/yyyy',
            background='darkblue',
            foreground='white',
            borderwidth=2
        )
        self.due_date_entry.grid(row=3, column=1, sticky='we', pady=5, padx=10)
        
        # Quantity
        ttk.Label(frame, text="Jumlah Pinjam:").grid(row=4, column=0, sticky='w', pady=5, padx=10)
        self.borrow_quantity_entry = ttk.Entry(frame)
        self.borrow_quantity_entry.grid(row=4, column=1, sticky='we', pady=5, padx=10)
        self.borrow_quantity_entry.insert(0, "1")  # Default value
        
        # Button
        borrow_button = ttk.Button(frame, text="Proses Peminjaman", command=self.process_borrowing)
        borrow_button.grid(row=5, column=1, sticky='e', pady=10, padx=10)
        
        # Configure grid weights
        frame.columnconfigure(1, weight=1)
        
        # Load available items
        self.load_available_items()
    
    def setup_return_frame(self, frame):
        # Transaction selection
        ttk.Label(frame, text="Transaksi Peminjaman:").grid(row=0, column=0, sticky='w', pady=5, padx=10)
        
        self.return_trans_combobox = ttk.Combobox(frame, state='readonly')
        self.return_trans_combobox.grid(row=0, column=1, sticky='we', pady=5, padx=10)
        
        # Return notes
        ttk.Label(frame, text="Catatan:").grid(row=1, column=0, sticky='w', pady=5, padx=10)
        self.return_notes_entry = ttk.Entry(frame)
        self.return_notes_entry.grid(row=1, column=1, sticky='we', pady=5, padx=10)
        
        # Button
        return_button = ttk.Button(frame, text="Proses Pengembalian", command=self.process_return)
        return_button.grid(row=2, column=1, sticky='e', pady=10, padx=10)
        
        # Configure grid weights
        frame.columnconfigure(1, weight=1)
        
        # Load borrowed items
        self.load_borrowed_items()
    
    def setup_history_frame(self, frame):
        # Treeview for transaction history
        columns = ('id', 'item_name', 'type', 'borrower', 'date', 'due_date', 'quantity')
        self.history_tree = ttk.Treeview(
            frame, 
            columns=columns, 
            show='headings',
            selectmode='browse'
        )
        
        # Configure columns
        self.history_tree.heading('id', text='ID')
        self.history_tree.column('id', width=50, anchor='center')
        
        self.history_tree.heading('item_name', text='Nama Barang')
        self.history_tree.column('item_name', width=200)
        
        self.history_tree.heading('type', text='Jenis')
        self.history_tree.column('type', width=100, anchor='center')
        
        self.history_tree.heading('borrower', text='Peminjam')
        self.history_tree.column('borrower', width=150)
        
        self.history_tree.heading('date', text='Tanggal')
        self.history_tree.column('date', width=120)
        
        self.history_tree.heading('due_date', text='Jatuh Tempo')
        self.history_tree.column('due_date', width=120)
        
        self.history_tree.heading('quantity', text='Jumlah')
        self.history_tree.column('quantity', width=80, anchor='center')
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.history_tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Load transaction history
        self.load_transaction_history()
    
    def create_import_export_tab(self):
        # Import/Export Tab
        ie_tab = ttk.Frame(self.notebook)
        self.notebook.add(ie_tab, text="Import/Export")
        
        # Export frame
        export_frame = ttk.LabelFrame(ie_tab, text="Export Data", padding=10)
        export_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(export_frame, text="Export ke JSON", command=self.export_to_json).pack(side='left', padx=5)
        ttk.Button(export_frame, text="Export ke PDF", command=self.export_to_pdf).pack(side='left', padx=5)
        
        # Import frame
        import_frame = ttk.LabelFrame(ie_tab, text="Import Data", padding=10)
        import_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(import_frame, text="Import dari JSON", command=self.import_from_json).pack(side='left', padx=5)
    
    # Item management methods
    def generate_barcode(self):
        """Generate a unique barcode for new items"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"ITEM-{timestamp}"
    
    def upload_photo(self):
        """Handle photo upload and display preview"""
        file_path = filedialog.askopenfilename(
            title="Pilih Foto Barang",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png")]
        )
        
        if file_path:
            self.photo_path = file_path
            
            # Display preview
            try:
                image = Image.open(file_path)
                image.thumbnail((200, 200))
                photo = ImageTk.PhotoImage(image)
                
                self.photo_preview = photo  # Keep reference
                self.photo_preview_label.config(image=photo)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal memuat gambar: {str(e)}")
    
    def save_item(self):
        """Save new item to database"""
        # Validate input
        name = self.name_entry.get().strip()
        quantity = self.quantity_entry.get().strip()
        
        if not name:
            messagebox.showerror("Error", "Nama barang harus diisi")
            return
        if not quantity or not quantity.isdigit():
            messagebox.showerror("Error", "Jumlah harus angka")
            return
        
        # Prepare item data
        item_data = {
            'name': name,
            'barcode': self.generate_barcode(),
            'quantity': int(quantity),
            'location': self.location_entry.get().strip(),
            'condition': self.condition_combobox.get(),
            'status': self.status_combobox.get(),
            'photo_path': self.photo_path
        }
        
        # Save to database
        item_id = self.db.add_item(item_data)
        if item_id:
            messagebox.showinfo("Sukses", "Barang berhasil disimpan")
            self.clear_form()
            self.load_available_items()
            
            # Generate barcode image
            self.generate_barcode_image(item_data['barcode'])
            
            # Update search tab
            self.show_all_items()
    
    def generate_barcode_image(self, barcode_text):
        """Generate barcode image and save to barcodes directory"""
        try:
            # Create barcodes directory if not exists
            os.makedirs('barcodes', exist_ok=True)
            
            # Generate barcode
            code = barcode.get('code128', barcode_text, writer=ImageWriter())
            filename = code.save(f'barcodes/{barcode_text}')
        except Exception as e:
            messagebox.showerror("Error", f"Gagal generate barcode: {str(e)}")
    
    def update_item(self):
        """Update existing item"""
        if not self.current_item_id:
            return
            
        # Validate input
        name = self.name_entry.get().strip()
        quantity = self.quantity_entry.get().strip()
        
        if not name:
            messagebox.showerror("Error", "Nama barang harus diisi")
            return
        if not quantity or not quantity.isdigit():
            messagebox.showerror("Error", "Jumlah harus angka")
            return
        
        # Prepare item data
        item_data = {
            'name': name,
            'quantity': int(quantity),
            'location': self.location_entry.get().strip(),
            'condition': self.condition_combobox.get(),
            'status': self.status_combobox.get(),
            'photo_path': self.photo_path
        }
        
        # Update in database
        if self.db.update_item(self.current_item_id, item_data):
            messagebox.showinfo("Sukses", "Barang berhasil diupdate")
            self.clear_form()
            self.show_all_items()
    
    def clear_form(self):
        """Clear the input form"""
        self.current_item_id = None
        self.photo_path = None
        self.photo_preview = None
        
        self.name_entry.delete(0, 'end')
        self.quantity_entry.delete(0, 'end')
        self.location_entry.delete(0, 'end')
        self.condition_combobox.set("Baik")
        self.status_combobox.set("Tersedia")
        self.barcode_label.config(text="(Akan digenerate otomatis)")
        self.photo_preview_label.config(image='')
        
        self.save_button.config(state='normal')
        self.update_button.config(state='disabled')
    
    # Search methods
    def search_items(self):
        """Search items based on search term"""
        search_term = self.search_entry.get().strip()
        if not search_term:
            self.show_all_items()
            return
        
        results = self.db.search_items(search_term)
        self.display_search_results(results)
    
    def show_all_items(self):
        """Show all items in the database"""
        items = self.db.get_all_items()
        self.display_search_results(items)
    
    def display_search_results(self, items):
        """Display search results in the treeview"""
        # Clear current items
        for row in self.results_tree.get_children():
            self.results_tree.delete(row)
        
        # Add new items
        for item in items:
            self.results_tree.insert('', 'end', values=(
                item[0],  # id
                item[1],  # name
                item[3],  # quantity
                item[4],  # location
                item[5],  # condition
                item[6]   # status
            ))
    
    def view_item_details(self):
        """View details of selected item"""
        selected = self.results_tree.selection()
        if not selected:
            return
        
        item_id = self.results_tree.item(selected[0], 'values')[0]
        item = self.db.get_item(item_id)
        if not item:
            return
        
        # Show details in a new window
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"Detail Barang - {item[1]}")
        detail_window.geometry("500x400")
        
        # Main frame
        main_frame = ttk.Frame(detail_window)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Item details
        ttk.Label(main_frame, text=f"Nama: {item[1]}", font=('Arial', 10, 'bold')).pack(anchor='w', pady=5)
        ttk.Label(main_frame, text=f"Jumlah: {item[3]}").pack(anchor='w', pady=2)
        ttk.Label(main_frame, text=f"Lokasi: {item[4]}").pack(anchor='w', pady=2)
        ttk.Label(main_frame, text=f"Kondisi: {item[5]}").pack(anchor='w', pady=2)
        ttk.Label(main_frame, text=f"Status: {item[6]}").pack(anchor='w', pady=2)
        ttk.Label(main_frame, text=f"Barcode: {item[2]}").pack(anchor='w', pady=2)
        
        # Display photo if exists
        if item[7]:  # photo_path
            try:
                image = Image.open(item[7])
                image.thumbnail((200, 200))
                photo = ImageTk.PhotoImage(image)
                
                photo_label = ttk.Label(main_frame, image=photo)
                photo_label.image = photo  # Keep reference
                photo_label.pack(pady=10)
            except Exception as e:
                ttk.Label(main_frame, text="Foto tidak dapat dimuat").pack(pady=10)
        
        # Transaction history
        ttk.Label(main_frame, text="Riwayat Transaksi:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=10)
        
        # Treeview for transaction history
        columns = ('type', 'borrower', 'date', 'due_date', 'quantity')
        history_tree = ttk.Treeview(
            main_frame, 
            columns=columns, 
            show='headings',
            height=5
        )
        
        # Configure columns
        history_tree.heading('type', text='Jenis')
        history_tree.column('type', width=100, anchor='center')
        
        history_tree.heading('borrower', text='Peminjam')
        history_tree.column('borrower', width=150)
        
        history_tree.heading('date', text='Tanggal')
        history_tree.column('date', width=100)
        
        history_tree.heading('due_date', text='Jatuh Tempo')
        history_tree.column('due_date', width=100)
        
        history_tree.heading('quantity', text='Jumlah')
        history_tree.column('quantity', width=80, anchor='center')
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=history_tree.yview)
        history_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        history_tree.pack(fill='both', expand=True)
        
        # Load transaction history
        transactions = self.db.get_transactions(item_id)
        for trans in transactions:
            history_tree.insert('', 'end', values=(
                'Peminjaman' if trans[2] == 'borrow' else 'Pengembalian',
                trans[3],  # borrower
                trans[5],  # date
                trans[6] if trans[6] else '-',  # due_date
                trans[8]   # quantity
            ))
    
    def edit_selected_item(self):
        """Edit selected item from search results"""
        selected = self.results_tree.selection()
        if not selected:
            return
        
        item_id = self.results_tree.item(selected[0], 'values')[0]
        item = self.db.get_item(item_id)
        if not item:
            return
        
        # Switch to input tab
        self.notebook.select(0)
        
        # Fill the form
        self.current_item_id = item[0]
        self.name_entry.delete(0, 'end')
        self.name_entry.insert(0, item[1])
        
        self.quantity_entry.delete(0, 'end')
        self.quantity_entry.insert(0, str(item[3]))
        
        self.location_entry.delete(0, 'end')
        self.location_entry.insert(0, item[4] if item[4] else '')
        
        self.condition_combobox.set(item[5] if item[5] else 'Baik')
        self.status_combobox.set(item[6] if item[6] else 'Tersedia')
        
        self.barcode_label.config(text=item[2])
        
        # Load photo if exists
        self.photo_path = item[7]
        if item[7]:
            try:
                image = Image.open(item[7])
                image.thumbnail((200, 200))
                photo = ImageTk.PhotoImage(image)
                
                self.photo_preview = photo  # Keep reference
                self.photo_preview_label.config(image=photo)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal memuat gambar: {str(e)}")
        
        # Change button states
        self.save_button.config(state='disabled')
        self.update_button.config(state='normal')
    
    def delete_selected_item(self):
        """Delete selected item from search results"""
        selected = self.results_tree.selection()
        if not selected:
            return
        
        item_id = self.results_tree.item(selected[0], 'values')[0]
        
        if messagebox.askyesno("Konfirmasi", "Apakah Anda yakin ingin menghapus barang ini?"):
            if self.db.delete_item(item_id):
                messagebox.showinfo("Sukses", "Barang berhasil dihapus")
                self.show_all_items()
    
    # Transaction methods
    def load_available_items(self):
        """Load available items for borrowing"""
        items = self.db.get_all_items()
        available_items = [(item[0], item[1]) for item in items if item[6] == 'Tersedia' and item[3] > 0]
        
        # Update combobox
        self.borrow_item_combobox['values'] = [f"{item[1]} (ID: {item[0]})" for item in available_items]
    
    def load_borrowed_items(self):
        """Load borrowed items for returning"""
        transactions = self.db.get_transactions()
        borrowed_items = [trans for trans in transactions if trans[2] == 'borrow' and trans[7] == 0]
        
        # Update combobox
        self.return_trans_combobox['values'] = [
            f"ID: {trans[0]} - {trans[8]} (oleh {trans[3]}, Jatuh Tempo: {trans[6]}, Jumlah: {trans[8]})"
            for trans in borrowed_items
        ]
    
    def load_transaction_history(self):
        """Load all transactions for history tab"""
        transactions = self.db.get_transactions()
        
        # Clear current items
        for row in self.history_tree.get_children():
            self.history_tree.delete(row)
        
        # Add new items
        for trans in transactions:
            self.history_tree.insert('', 'end', values=(
                trans[0],  # id
                trans[8],  # item_name
                'Peminjaman' if trans[2] == 'borrow' else 'Pengembalian',
                trans[3],  # borrower
                trans[5],  # date
                trans[6] if trans[6] else '-',  # due_date
                trans[8]   # quantity
            ))
    
    def process_borrowing(self):
        """Process item borrowing"""
        selected_item = self.borrow_item_combobox.get()
        borrower = self.borrower_entry.get().strip()
        
        if not selected_item or not borrower:
            messagebox.showerror("Error", "Barang dan peminjam harus diisi")
            return
        
        # Extract item ID from selection
        try:
            item_id = int(selected_item.split('(ID: ')[1].rstrip(')'))
        except:
            messagebox.showerror("Error", "Pilih barang yang valid")
            return
        
        # Validate quantity
        quantity_text = self.borrow_quantity_entry.get().strip()
        if not quantity_text.isdigit() or int(quantity_text) <= 0:
            messagebox.showerror("Error", "Jumlah pinjam harus berupa angka lebih dari 0")
            return
        quantity = int(quantity_text)

        # Check availability
        item = self.db.get_item(item_id)
        if not item or item[3] < quantity:
            messagebox.showerror("Error", "Jumlah barang tidak mencukupi")
            return

        # Get date from DateEntry and convert to database format (YYYY-MM-DD)
        due_date = self.due_date_entry.get_date().strftime('%Y-%m-%d')

        # Prepare transaction data
        transaction_data = {
            'item_id': item_id,
            'type': 'borrow',
            'borrower': borrower,
            'purpose': self.purpose_entry.get().strip(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'due_date': due_date,
            'quantity': quantity
        }
        
        # Save transaction (single transaction with quantity)
        if self.db.add_transaction(transaction_data):
            messagebox.showinfo("Sukses", f"Peminjaman {quantity} unit berhasil diproses")
            
            # Clear form
            self.borrower_entry.delete(0, 'end')
            self.purpose_entry.delete(0, 'end')
            self.borrow_quantity_entry.delete(0, 'end')
            self.borrow_quantity_entry.insert(0, "1")  # Reset to default
            
            # Refresh data
            self.load_available_items()
            self.load_borrowed_items()
            self.load_transaction_history()
            self.show_all_items()
    
    def process_return(self):
        """Process item return"""
        selected_trans = self.return_trans_combobox.get()
        
        if not selected_trans:
            messagebox.showerror("Error", "Pilih transaksi peminjaman")
            return
        
        # Extract transaction ID from selection
        try:
            trans_id = int(selected_trans.split('ID: ')[1].split(' ')[0])
        except:
            messagebox.showerror("Error", "Pilih transaksi yang valid")
            return
        
        # Get transaction details
        conn = sqlite3.connect('inventaris.db')
        cursor = conn.cursor()
        cursor.execute('SELECT item_id, quantity FROM transactions WHERE id=?', (trans_id,))
        result = cursor.fetchone()
        item_id = result[0]
        quantity = result[1]
        conn.close()
        
        # Prepare return transaction
        transaction_data = {
            'item_id': item_id,
            'type': 'return',
            'borrower': 'System',
            'purpose': self.return_notes_entry.get().strip() or 'Pengembalian barang',
            'date': datetime.now().strftime('%Y-%m-%d'),
            'due_date': None,
            'quantity': quantity
        }
        
        # Save return transaction and mark original as returned
        conn = sqlite3.connect('inventaris.db')
        cursor = conn.cursor()
        
        try:
            # Add return transaction
            cursor.execute('''
            INSERT INTO transactions (item_id, type, borrower, purpose, date, due_date, quantity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                transaction_data['item_id'],
                transaction_data['type'],
                transaction_data['borrower'],
                transaction_data['purpose'],
                transaction_data['date'],
                transaction_data['due_date'],
                transaction_data['quantity']
            ))
            
            # Mark original as returned
            cursor.execute('''
            UPDATE transactions SET returned = 1 WHERE id = ?
            ''', (trans_id,))
            
            # Update item quantity
            cursor.execute('''
            UPDATE items SET quantity = quantity + ?, status = CASE 
                WHEN quantity + ? > 0 THEN 'Tersedia' 
                ELSE status 
            END WHERE id = ?
            ''', (quantity, quantity, item_id))
            
            conn.commit()
            messagebox.showinfo("Sukses", "Pengembalian berhasil diproses")
            
            # Clear form
            self.return_notes_entry.delete(0, 'end')
            
            # Refresh data
            self.load_available_items()
            self.load_borrowed_items()
            self.load_transaction_history()
            self.show_all_items()
        except sqlite3.Error as e:
            conn.rollback()
            messagebox.showerror("Database Error", str(e))
        finally:
            conn.close()
    
    def check_overdue_transactions(self):
        """Check for overdue transactions and show notification"""
        overdue = self.db.get_overdue_transactions()
        if overdue:
            messagebox.showwarning(
                "Peminjaman Melebihi Batas Waktu",
                f"Ada {len(overdue)} peminjaman yang melebihi batas waktu"
            )
    
    # Import/Export methods
    def export_to_json(self):
        """Export inventory data to JSON file"""
        # Get all items
        items = self.db.get_all_items()
        
        # Prepare data for export
        export_data = {
            'items': [
                {
                    'name': item[1],
                    'barcode': item[2],
                    'quantity': item[3],
                    'location': item[4],
                    'condition': item[5],
                    'status': item[6],
                    'photo_path': item[7]
                }
                for item in items
            ]
        }
        
        # Ask for save location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(export_data, f, indent=4)
                messagebox.showinfo("Sukses", f"Data berhasil diexport ke {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal export data: {str(e)}")
    
    def import_from_json(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if not file_path:
            return

        try:
            with open(file_path, 'r') as f:
                import_data = json.load(f)

            if 'items' not in import_data:
                messagebox.showerror("Error", "Format file tidak valid")
                return

            success_count = 0
            duplicate_count = 0
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            for item in import_data['items']:
                try:
                    # Cek apakah barcode sudah ada
                    cursor.execute("SELECT id FROM items WHERE barcode=?", (item.get('barcode'),))
                    if cursor.fetchone() is None:  # Barcode belum ada
                        # Generate barcode baru jika tidak ada di data impor
                        item['barcode'] = item.get('barcode') or self.generate_barcode()
                        cursor.execute('''
                            INSERT INTO items (name, barcode, quantity, location, condition, status, photo_path)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            item['name'],
                            item['barcode'],
                            item['quantity'],
                            item.get('location', ''),
                            item.get('condition', 'Baik'),
                            item.get('status', 'Tersedia'),
                            item.get('photo_path')
                        ))
                        success_count += 1
                    else:
                        duplicate_count += 1
                except sqlite3.Error as e:
                    logging.error(f"Gagal impor item {item.get('name')}: {str(e)}")
                    continue

            conn.commit()
            conn.close()

            message = f"Berhasil mengimpor {success_count} item"
            if duplicate_count > 0:
                message += f"\n{duplicate_count} item duplikat dilewati"
            messagebox.showinfo("Hasil Impor", message)
            self.show_all_items()

        except Exception as e:
            messagebox.showerror("Error", f"Gagal import data: {str(e)}")
    
    def export_to_pdf(self):
        """Export inventory report to PDF"""
        # Get all items
        items = self.db.get_all_items()
        
        # Create PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        # Add title
        pdf.cell(200, 10, txt="Laporan Inventaris Barang Sekolah", ln=1, align='C')
        pdf.ln(10)
        
        # Add date
        pdf.cell(200, 10, txt=f"Tanggal: {datetime.now().strftime('%d/%m/%Y')}", ln=1)
        pdf.ln(5)
        
        # Add table header
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(10, 10, "ID", border=1)
        pdf.cell(70, 10, "Nama Barang", border=1)
        pdf.cell(20, 10, "Jumlah", border=1)
        pdf.cell(40, 10, "Lokasi", border=1)
        pdf.cell(30, 10, "Kondisi", border=1)
        pdf.cell(30, 10, "Status", border=1, ln=1)
        
        # Add items
        pdf.set_font("Arial", size=10)
        for item in items:
            pdf.cell(10, 10, str(item[0]), border=1)
            pdf.cell(70, 10, item[1], border=1)
            pdf.cell(20, 10, str(item[3]), border=1)
            pdf.cell(40, 10, item[4] if item[4] else '-', border=1)
            pdf.cell(30, 10, item[5] if item[5] else '-', border=1)
            pdf.cell(30, 10, item[6] if item[6] else '-', border=1, ln=1)
        
        # Add summary
        pdf.ln(10)
        pdf.cell(200, 10, txt=f"Total Barang: {len(items)}", ln=1)
        
        # Ask for save location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")]
        )
        
        if file_path:
            try:
                pdf.output(file_path)
                messagebox.showinfo("Sukses", f"Laporan berhasil diexport ke {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal export PDF: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = InventoryApp(root)
    root.mainloop()