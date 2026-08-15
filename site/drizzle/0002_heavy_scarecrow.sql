ALTER TABLE `apartment_posts` ADD `analysis_status` text DEFAULT 'pending' NOT NULL;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `analysis_attempts` integer DEFAULT 0 NOT NULL;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `analysis_claim_id` text;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `analysis_worker` text;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `analysis_claimed_at` text;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `analyzed_at` text;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `analysis_model` text;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `location_text` text;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `geocoded_address` text;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `latitude` real;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `longitude` real;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `location_confidence` text;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `condition_signal` text;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `move_in_signal` text;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `walk_to_work_minutes` integer;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `walk_to_work_meters` integer;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `walk_to_sarona_minutes` integer;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `walk_to_sarona_meters` integer;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `analysis_payload` text;--> statement-breakpoint
ALTER TABLE `apartment_posts` ADD `analysis_error` text;--> statement-breakpoint
CREATE INDEX `idx_apartment_posts_analysis_queue` ON `apartment_posts` (`analysis_status`,`received_at`);