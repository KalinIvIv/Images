import sys


def run():
    args = sys.argv[1:]
    if any(a.startswith('chrome-extension://') for a in args):
        from photocut import host
        host.main()
    elif args:
        from photocut import cli
        sys.exit(cli.main(args))
    else:
        # Double-clicked: register with Chrome and say what to do next.
        from photocut import config, install
        install.install()
        text = ('PhotoCut is registered with Chrome.\n\n'
                'Next: load the extension in Chrome (see README), then open its Options\n'
                'to choose your output folder and the shared rules file.\n\n'
                f'Settings file: {config.config_path()}')
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo('PhotoCut', text)
            root.destroy()
        except Exception:
            print(text)


if __name__ == '__main__':
    run()
