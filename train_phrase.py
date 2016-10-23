import tensorflow as tf
import argparse
import phraseConfig
import phrase_model 
import accuracy
import reader
import annotator
import gpu_access
import numpy as np


def run_epoch(sess, model, train_step, model_loss, rd, saver, config):
	rd.reset_counter()
	rd.reset_counter_by_concept()

	'''
	batch = rd.read_batch(50, newConfig.comp_size)
	batch_feed = {model.input_sequence : batch[0], model.input_sequence_lengths: batch[1], model.input_hpo_id:batch[2]}
	print sess.run(model.new_loss, feed_dict = batch_feed).shape
	exit()
	'''

	ii = 0
	loss = 0
	report_len = 20
	while True:
		batch = rd.read_batch(config.batch_size) #, config.comp_size)
		#batch = rd.read_batch_by_concept(config.batch_size) #, config.comp_size)
		if ii == 10000000 or batch == None:
			break
		#print np.array(batch['hp_id']).T[0]
		#batch_feed = {model.input_sequence : batch['seq'], model.input_sequence_lengths: batch['seq_len'], model.input_hpo_id:batch['hp_id']} #, model.input_hpo_id_unique:batch['hp_id']} #, model.set_loss_for_input:True, model.set_loss_for_def:False}
		batch_feed = {model.input_sequence : batch['seq'], model.input_sequence_lengths: batch['seq_len'], model.input_hpo_id:batch['hp_id'], model.input_hpo_id_unique:np.array(list(set(batch['hp_id'])))} #, model.set_loss_for_input:True, model.set_loss_for_def:False}

		_ , step_loss = sess.run([train_step, model_loss], feed_dict = batch_feed)
		loss += step_loss

		if ii % report_len == report_len-1:
			print "Step =", ii+1, "\tLoss =", loss/report_len
			loss = 0
		ii += 1

def train(repdir, lr_init, lr_decay):
	print "Training..."

	oboFile = open("data/hp.obo")
	vectorFile = open("data/vectors.txt")

	rd = reader.Reader(oboFile, vectorFile)
	print "reader inited"
	#rd.init_uberon_list()
	config = phraseConfig.Config
	config.update_with_reader(rd)
	
	model = phrase_model.NCRModel(config, training=True)
	model_loss = model.input_losses
	#model_loss = tf.reduce_mean(model.input_losses)

	lr = tf.Variable(0.01, trainable=False)
#	train_step_input_only = tf.train.AdamOptimizer(lr).minimize(tf.reduce_mean(model.input_losses))
	train_step = tf.train.AdamOptimizer(lr).minimize(model_loss)
#	train_step_input_and_def = tf.train.AdamOptimizer(lr).minimize(tf.reduce_mean(tf.concat(0,[model.input_losses, model.def_losses]))

	sess = tf.Session(config=tf.ConfigProto(allow_soft_placement=True))
	sess.run(tf.initialize_all_variables())
	sess.run(tf.assign(model.word_embedding, rd.word2vec))
	sess.run(tf.assign(model.ancestry_masks, rd.ancestry_mask))
	
	saver = tf.train.Saver()

	samplesFile = open("data/labeled_data")
	ant = annotator.NeuralPhraseAnnotator(model, rd, sess, False)
	samples = accuracy.prepare_phrase_samples(rd, samplesFile)

	training_samples = {}
	for hpid in rd.names:
		for s in rd.names[hpid]:
			training_samples[s]=[hpid]

	with open(repdir+"/test_results.txt","w") as testResultFile:
		testResultFile.write("")

	for epoch in range(20):
		print "epoch ::", epoch

		lr_new = lr_init * (lr_decay ** max(epoch-4.0, 0.0))
		sess.run(tf.assign(lr, lr_new))

		run_epoch(sess, model, train_step, model_loss, rd, saver, config)

		hit, total = accuracy.find_phrase_accuracy(ant, samples, 5, False)
		print "Accuracy on test set ::", float(hit)/total
		with open(repdir+"/test_results.txt","a") as testResultFile:
			testResultFile.write(str(float(hit)/total)+"\n")
		
		'''
		hit, total = ant.find_accuracy(training_samples, 5)
		print "Accuracy on training set ::", float(hit)/total
		'''

	saver.save(sess, repdir+'/training.ckpt') ## TODO


def main():
	parser = argparse.ArgumentParser(description='Hello!')
	parser.add_argument('--repdir', help="The location where the checkpoints and the logfiles will be stored, default is \'checkpoints/\'", default="checkpoints/")
	args = parser.parse_args()


	lr_init = 0.01
	lr_decay = 0.8

	board = gpu_access.get_gpu()
	with tf.device('/gpu:'+board):
		train(args.repdir, lr_init, lr_decay)

if __name__ == "__main__":
	main()

