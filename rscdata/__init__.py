import logging

from .rscdata import RscData

def setup(bot):
    global logger
    ensure_data_folder()
    logger = logging.getLogger("rsc.data")
    if logger.level == 0:
        # Prevents the logger from being loaded again in case of module reload
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(
            filename=RscData.LOG_FILE, encoding='utf-8', mode='a')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(message)s', datefmt="[%d/%m/%Y %H:%M]"))
        logger.addHandler(handler)
    bot.add_cog(RscData(bot))