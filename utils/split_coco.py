import argparse
import json
from pathlib import Path

def split_coco_sequential(annotation_file, output_dir, train_count=7000, val_count=2000, test_count=1000):
    
    with open(annotation_file, 'r') as f:
        coco_data = json.load(f)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    image_ids = [img['id'] for img in coco_data['images']]
    
    train_ids = set(image_ids[:train_count])
    val_ids = set(image_ids[train_count:train_count + val_count])
    test_ids = set(image_ids[train_count + val_count:train_count + val_count + test_count])
    
    print(f"Total images: {len(image_ids)}")
    print(f"Train: {len(train_ids)}, Val: {len(val_ids)}, Test: {len(test_ids)}")
    
    splits = {
        'train': train_ids,
        'val': val_ids,
        'test': test_ids
    }
    
    for split_name, split_image_ids in splits.items():
        split_images = [img for img in coco_data['images'] if img['id'] in split_image_ids]

        split_annotations = [ann for ann in coco_data['annotations'] if ann['image_id'] in split_image_ids]
        
        # Create new COCO dataset
        split_data = {
            'info': coco_data['info'],
            'licenses': coco_data['licenses'],
            'categories': coco_data['categories'],
            'images': split_images,
            'annotations': split_annotations
        }
        output_file = Path(output_dir) / f"instances_{split_name}.json"
        with open(output_file, 'w') as f:
            json.dump(split_data, f, indent=2)
        
        print(f"Saved {split_name}: {len(split_images)} images, {len(split_annotations)} annotations")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split COCO annotations into train, val, and test sets")
    parser.add_argument('--annotation-file', '-a', required=True, help='Path to the COCO annotation JSON file')
    parser.add_argument('--output-dir', '-o', required=True, help='Output directory for split annotation files')
    parser.add_argument('--train-count', '-tr', type=int, default=7000, help='Number of images for training (default: 7000)')
    parser.add_argument('--val-count', '-v', type=int, default=2000, help='Number of images for validation (default: 2000)')
    parser.add_argument('--test-count', '-te', type=int, default=1000, help='Number of images for testing (default: 1000)')
    
    args = parser.parse_args()
    
    split_coco_sequential(
        annotation_file=args.annotation_file,
        output_dir=args.output_dir,
        train_count=args.train_count,
        val_count=args.val_count,
        test_count=args.test_count
    )
