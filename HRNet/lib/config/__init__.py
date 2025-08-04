import yaml
from yacs.config import CfgNode as CN

# Mock configuration
cfg = CN()
cfg.MODEL = CN()
cfg.MODEL.NAME = 'pose_hrnet'
cfg.MODEL.NUM_JOINTS = 294
cfg.MODEL.IMAGE_SIZE = [288, 384]
cfg.MODEL.HEATMAP_SIZE = [72, 96]
cfg.MODEL.EXTRA = CN()
cfg.MODEL.EXTRA.FINAL_CONV_KERNEL = 1

def update_config(cfg, args):
    """Mock function to update config from args"""
    if hasattr(args, 'cfg') and args.cfg:
        try:
            with open(args.cfg, 'r') as f:
                config = yaml.safe_load(f)
                # Basic config updates would go here
        except:
            pass  # Use default config if file doesn't exist
    return cfg 