# -*- coding: utf-8 -*-
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(filename)s[line:%(lineno)d] - %(message)s'
        },
        'simple': {
            'format': '%(asctime)s - %(levelname)s - %(message)s'
        },
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(pathname)s[line:%(lineno)d] - %(funcName)s - %(message)s'
        },
        'colored_standard': {
            '()': 'colorlog.ColoredFormatter',
            'format': '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(filename)s[line:%(lineno)d - %(message)s',
            'log_colors': {
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white'
            }
        },
        'colored_simple': {
            '()': 'colorlog.ColoredFormatter',
            'format': '%(log_color)s%(asctime)s - %(levelname)s - %(message)s',
            'log_colors': {
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white'
            }
        }
    },

    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'colored_simple',
            'stream': 'ext://sys.stdout'
        },
        'debug_console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'colored_standard',
            'stream': 'ext://sys.stdout'
        }
    },

    'loggers': {
        '': {
            'level': 'DEBUG',
            'handlers': ['debug_console'],
            'propagate': False
        },
        'app': {
            'level': 'DEBUG',
            'handlers': ['console'],
            'propagate': False
        },
        'database': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': False
        },
        'api': {
            'level': 'DEBUG',
            'handlers': ['debug_console'],
            'propagate': False
        }
    }
}
