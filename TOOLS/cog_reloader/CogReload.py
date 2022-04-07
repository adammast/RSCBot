import config
import tkinter as tk
import os
from functools import partial
from datetime import datetime
import time
import shutil


def clean_date_time(date_time: str):
    while date_time[0] == "0":
        date_time = date_time[1:]
    return date_time


def get_last_modified(cog_name: str):
    today = datetime.date(datetime.now())
    last_modified = os.path.getmtime("{}/{}/{}.py".format(config.target_repo, cog_name, cog_name))
    time_format = "%I:%M:%S %p" if config.am_pm_format else "%H:%M:%S"
    time_lm = time.strftime(time_format, time.localtime(last_modified))
    date_lm = time.strftime("%Y-%m-%d", time.localtime(last_modified))
    if str(date_lm) == str(today):
        return clean_date_time(time_lm)
    return clean_date_time(time.strftime("%m/%d/%Y", time.localtime(last_modified)))


def get_time():
    t = time.localtime()
    if config.am_pm_format:
        current_time = time.strftime("%I:%M:%S %p", t)
        return clean_date_time(current_time)


def get_cogs_in_folder(folder_path):
    for root, dirs, files in os.walk(folder_path):
        return dirs


def update_cog(cog_name: str, label: tk.Label):
    source_path = "{}/{}".format(config.source_repo, cog_name)
    # for file_name in os.listdir(source_path):
    #     if os.path.isfile(os.path.join(source_path, file_name)) and ".py" in str(file_name):
    #         source = "{}/{}/{}".format(config.source_repo, cog_name, file_name)
    #         target = "{}/{}/{}".format(config.target_repo, cog_name, file_name)
    #         shutil.copyfile(source, target)
    for file_name in os.listdir(source_path):
        if not os.path.isfile(os.path.join(source_path, file_name)) and ".py" in str(file_name):
            continue
        source_file = "{}/{}/{}".format(config.source_repo, cog_name, file_name)
        target_file = "{}/{}/{}".format(config.target_repo, cog_name, file_name)
        with open(source_file, 'r') as source, open(target_file, 'w') as target:
            shutil.copyfileobj(source, target)

    print("{} reloaded.".format(cog_name))
    label['text'] = get_time()


def main():
    source_cogs = get_cogs_in_folder(config.source_repo)
    target_cogs = get_cogs_in_folder(config.target_repo)

    shared_cogs = []
    for cog_name in source_cogs:
        if cog_name in target_cogs:
            shared_cogs.append(cog_name)

    window = tk.Tk()
    proj = config.source_repo[config.source_repo.rindex("/")+1:]
    window.title("{} Cog Reloader".format(proj))
    for i in range(0, len(shared_cogs)):
        cog_name = shared_cogs[i]
        cog_ts_label = tk.Label(window, text=get_last_modified(cog_name))
        button = tk.Button(
            window,
            text="Reload {}".format(cog_name),
            command=partial(update_cog, cog_name, cog_ts_label),
            height=config.button_height,
            width=config.button_width
            )

        button.grid(row=i+1, column=0, padx=config.padx, pady=config.pady)
        cog_ts_label.grid(row=i+1, column=1, padx=config.padx, pady=config.pady)

    tk.Label(window, text="{} Cogs".format(proj)).grid(row=0, column=0, padx=config.padx, pady=config.pady)
    tk.Label(window, text="Last Updated").grid(row=0, column=1, padx=config.padx, pady=config.pady)

    window.anchor("n")
    window.mainloop()


if __name__ == '__main__':
    main()
