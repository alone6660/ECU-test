from Commonlib.Canoedevice.Canoe_device import CANoeSingleton
from Commonlib.logger.logger import setup_logging

logger = setup_logging()
canoe = CANoeSingleton(canoe_cfg=r"E:\workspace\Autotest\Canoe\00_Project\F520M_ESC20\F520M_ESC20_12.cfg")