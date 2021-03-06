import sys
sys.path.append('../')

import torch

from tools import *


def warmup_feature_module_a_step(config, base, loaders):
	'''
	when warm up the feature module, use only infrared images
	:param config:
	:param base:
	:param loaders:
	:return:
	'''

	base.set_train()
	feature_meter = AverageMeter()

	for _ in range(100):

		## load ir data
		rgb_images, rgb_pids, _, _ = loaders.rgb_train_iter_ide.next_one()
		rgb_images, rgb_pids = rgb_images.to(base.device), rgb_pids.to(base.device)
		ir_images, ir_pids, _, _ = loaders.ir_train_iter_ide.next_one()
		ir_images, ir_pids = ir_images.to(base.device), ir_pids.to(base.device)

		## forward
		rgb_feature1, rgb_feature2 = base.encoder_rgb(base.process_images_4_encoder(rgb_images, True, True))
		ir_feature1, ir_feature2 = base.encoder_ir(base.process_images_4_encoder(ir_images, True, True))
		_, class_optim1, class_optim2, class_optim3, embed_optim1, embed_optim2, embed_optim3 = base.embeder(ir_feature1, ir_feature2, rgb_feature1, rgb_feature2)

		## compute losses
		# rgb_acc_1, loss_rgb_cls_1 = base.compute_classification_loss(class_optim1, rgb_pids)
		# rgb_acc_2, loss_rgb_cls_2 = base.compute_classification_loss(class_optim2, rgb_pids)
		# rgb_acc_3, loss_rgb_cls_3 = base.compute_classification_loss(class_optim3, rgb_pids)
		# # print(loss_ir_cls_1, loss_ir_cls_2, loss_ir_cls_3)
		# # print(ir_acc_1, ir_acc_2, ir_acc_3)
		# loss_rgb_cls = (loss_rgb_cls_1 + loss_rgb_cls_2 + loss_rgb_cls_3) / 3
		# rgb_acc = (rgb_acc_1[0] + rgb_acc_2[0] + rgb_acc_3[0]) / 3
		# # triplet loss
		# loss_rgb_triplet = base.compute_triplet_loss(embed_optim3, embed_optim3, embed_optim3, rgb_pids, rgb_pids,
		# 										 rgb_pids)
		# loss_rgb = loss_rgb_cls + loss_rgb_triplet


		# classification loss
		ir_acc_1, loss_ir_cls_1 = base.compute_classification_loss(class_optim1, ir_pids)
		ir_acc_2, loss_ir_cls_2 = base.compute_classification_loss(class_optim2, ir_pids)
		ir_acc_3, loss_ir_cls_3 = base.compute_classification_loss(class_optim3, ir_pids)
		# print(loss_ir_cls_1, loss_ir_cls_2, loss_ir_cls_3)
		# print(ir_acc_1, ir_acc_2, ir_acc_3)
		loss_ir_cls = (loss_ir_cls_1 + loss_ir_cls_2 + loss_ir_cls_3) / 3
		ir_acc = (ir_acc_1[0] + ir_acc_2[0] + ir_acc_3[0]) / 3
		# triplet loss
		loss_ir_triplet = base.compute_triplet_loss(embed_optim3, embed_optim3, embed_optim3, ir_pids, ir_pids,
												 ir_pids)
		loss_ir = loss_ir_cls + loss_ir_triplet

		loss_all = loss_ir

		## optimize
		base.ide_optimizer.zero_grad()
		loss_all.backward()
		base.ide_optimizer.step()


		# record
		torch.Tensor([ ir_acc ,loss_ir_cls.data, loss_ir_triplet.data])
		feature_meter.update(torch.Tensor([ ir_acc, loss_ir_cls.data, loss_ir_triplet.data]), 1)

	return [ 'ir_acc', 'loss_ir_cls', 'loss_ir_triplet'], feature_meter.get_val_numpy()



def warmup_pixel_module_a_step(config, base, loaders):

	base.set_train()

	pixel_meter = AverageMeter(neglect_value=99.99)
	for _ in range(100):
		pixel_titles, pixel_values = warmup_pixel_module_an_iter(config, base, loaders)
		pixel_meter.update(pixel_values, 1)

	return pixel_titles, pixel_meter.get_val_numpy()



def warmup_pixel_module_an_iter(config, base, loaders):

	#########################################################################################################
	#                                                     Data                                              #
	#########################################################################################################
	## images
	real_rgb_images, rgb_pids, _, _ = loaders.rgb_train_iter_gan.next_one()
	real_ir_images, ir_pids, _, _ = loaders.ir_train_iter_gan.next_one()
	real_rgb_images, real_ir_images = real_rgb_images.to(base.device), real_ir_images.to(base.device)
	rgb_pids, ir_pids = rgb_pids.to(base.device), ir_pids.to(base.device)

	## fake images
	fake_rgb_images = base.G_ir2rgb(real_ir_images)
	fake_ir_images = base.G_rgb2ir(real_rgb_images)

	## features
	real_ir_features1, real_ir_features2 = base.encoder_ir(base.process_images_4_encoder(real_ir_images, True, True))
	fake_ir_features1, fake_ir_features2 = base.encoder_ir(base.process_images_4_encoder(fake_ir_images, True, True))
	real_rgb_features1, real_rgb_features2 = base.encoder_rgb(base.process_images_4_encoder(real_rgb_images, True, True))
	fake_rgb_features1, fake_rgb_features2 = base.encoder_rgb(base.process_images_4_encoder(real_rgb_images, True, True))

	#########################################################################################################
	#                                                     Generator                                         #
	#########################################################################################################
	## gan loss
	gan_loss_rgb = base.criterion_gan_mse(base.D_rgb_warmup(fake_rgb_images), base.ones)
	gan_loss_ir = base.criterion_gan_mse(base.D_ir_warmup(fake_ir_images), base.ones)
	gan_loss = (gan_loss_rgb + gan_loss_ir) / 2.0

	## cycle loss
	cycle_loss_rgb = base.criterion_gan_cycle(base.G_ir2rgb(fake_ir_images), real_rgb_images)
	cycle_loss_ir = base.criterion_gan_cycle(base.G_rgb2ir(fake_rgb_images), real_ir_images)
	# print(cycle_loss_rgb, cycle_loss_ir)

	cycle_loss = (cycle_loss_rgb + cycle_loss_ir) / 2.0

	## idnetity loss
	identity_loss_rgb = base.criterion_gan_identity(base.G_ir2rgb(real_rgb_images), real_rgb_images)
	identity_loss_ir = base.criterion_gan_identity(base.G_rgb2ir(real_ir_images), real_ir_images)
	identity_loss = (identity_loss_rgb + identity_loss_ir) / 2.0

	## task related loss
	_, _, _, _,_,_,real_ir_embedding_list = base.embeder(real_ir_features1, real_ir_features2, fake_rgb_features1, fake_rgb_features2 )
	_, _, _,fake_ir_logit_list,_,_,fake_ir_embedding_list = base.embeder(fake_ir_features1, fake_ir_features2, real_rgb_features1, real_rgb_features2)



	tri_loss_1 = base.compute_triplet_loss(fake_ir_embedding_list, real_ir_embedding_list,
	                                       real_ir_embedding_list, rgb_pids, ir_pids, ir_pids)
	tri_loss_2 = base.compute_triplet_loss(real_ir_embedding_list, fake_ir_embedding_list,
	                                       fake_ir_embedding_list, rgb_pids, ir_pids, ir_pids)

	_, cls_loss = base.compute_classification_loss(fake_ir_logit_list, rgb_pids)

	## overall loss and optimize
	g_loss = gan_loss + 10 * cycle_loss + 5 * identity_loss + \
	         base.lambda_pixel_tri * (tri_loss_1 + tri_loss_2) + base.lambda_pixel_cls * cls_loss

	base.G_optimizer.zero_grad()
	g_loss.backward(retain_graph=True)
	base.G_optimizer.step()

	#########################################################################################################
	#                                                     Discriminator                                     #
	#########################################################################################################
	# discriminator rgb
	gan_loss_rgb_real = base.criterion_gan_mse(base.D_rgb_warmup(real_rgb_images), base.ones)
	gan_loss_rgb_fake = base.criterion_gan_mse(base.D_rgb_warmup(fake_rgb_images.detach()), base.zeros)
	gan_loss_rgb = (gan_loss_rgb_real + gan_loss_rgb_fake) / 2.0

	base.D_rgb_optimizer.zero_grad()
	gan_loss_rgb.backward()
	base.D_rgb_optimizer.step()

	# discriminator ir
	gan_loss_ir_real = base.criterion_gan_mse(base.D_ir_warmup(real_ir_images), base.ones)
	gan_loss_ir_fake = base.criterion_gan_mse(base.D_ir_warmup(fake_ir_images.detach()), base.zeros)
	gan_loss_ir = (gan_loss_ir_real + gan_loss_ir_fake) / 2.0

	base.D_ir_optimizer.zero_grad()
	gan_loss_ir.backward()
	base.D_ir_optimizer.step()

	return ['G_GAN', 'CYC', 'IDENT', 'D_GAN', 'TRI', 'CLS'], \
	       torch.Tensor([gan_loss.data, cycle_loss.data, identity_loss.data, (gan_loss_rgb + gan_loss_ir).data,
	                     (tri_loss_1 + tri_loss_2).data, cls_loss.data])




