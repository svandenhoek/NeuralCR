import argparse
import phrase_model 
import accuracy
import fasttext_reader as reader
import numpy as np
import sys
import sent_accuracy
import time
import os
import h5py
from onto import Ontology
import fasttext
from eval import eval

class Ensemle():
    def __init__(self, models, ont):
        self.models = models
        self.ont = ont

    def get_probs(self, querry):
        for i,m in enumerate(self.models):
            if i==0:
                res_querry = m.get_probs(querry)
            else:
                res_querry += m.get_probs(querry)
        return res_querry/len(self.models)

    def get_hp_id(self, querry, count=1):
        res_querry = self.get_probs(querry)
        results=[]
        for s in range(len(querry)):
            indecies_querry = np.argsort(-res_querry[s,:])

            tmp_res = []
            for i in indecies_querry:
                '''
                print i
                '''
                if i == len(self.ont.concepts):
                    tmp_res.append(('None',res_querry[s,i]))
                else:
                    tmp_res.append((self.ont.concepts[i],res_querry[s,i]))
                if len(tmp_res)>=count:
                        break
            results.append(tmp_res)

        return results

def create_output_dir(model, theta, data_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    ct=0
    for filename in os.listdir(data_dir):
        ct+=1
        #if ct%5==0:
        #    print ct
        #if ct ==10:
        #    break
        #if os.path.isfile(output_dir+"/"+filename):
        #    continue
        text = open(data_dir+filename).read()
        predictions = model.process_text(text, theta)
 
        with open(output_dir+"/"+filename,"w") as fw:
            for y in predictions:
                fw.write(y[2]+"\n")

def print_res(results):
    res_print = []
    for style in ["micro", "vanila"]: 
        for acc_type in ["precision", "recall", "fmeasure"]: 
            res_print.append(results[style][acc_type])
    if 'jaccard' in results:
        res_print.append(results['jaccard'])
        return "%.4f & %.4f & %.4f & %.4f & %.4f & %.4f & %.4f\\\\" % tuple(res_print)
    else:
        return "%.4f & %.4f & %.4f & %.4f & %.4f & %.4f\\\\" % tuple(res_print)

def mimic_experiment(model, exp_name):
    outfile = open("report_" + exp_name + ".txt","a")
    print "Exp:", exp_name
    outfile.write("Exp: " + exp_name +"\n")
    outfile.flush()


    num_epochs = 50 ##
    for epoch in range(num_epochs):
        model.train_epoch(verbose=False)
    print "model trained"

    param_dir = "params_"+exp_name
    if not os.path.exists(param_dir):
        os.makedirs(param_dir)
    model.save_params(param_dir)

    import json
    with open('data/snomed2icd.json', 'r') as fp:
        snomed2icd = json.load(fp)

    mimic_dir = "../../datasets/small_mimic/"
    texts = dict([(f,open(mimic_dir+'/text/'+f).read()) for f in os.listdir(mimic_dir+"/text/")])
    labels ={}
    for key in os.listdir(mimic_dir+"/labels/"):
        labels[key]=set([icd.strip() for icd in open(mimic_dir+"/labels/"+key).readlines() if icd.strip() in snomed2icd.values()])

    threshold = 0.8

    def eval_omim(keys, threshold):
        total_precision = 0
        total_recall = 0
        total_docs = 0

        total_relevant = 0
        total_positives = 0
        total_true_pos = 0
        for key in keys: ##
            ans = model.process_text(texts[key],threshold)
            positives = set([snomed2icd[x[2]] for x in ans])
            real=labels[key]
            true_pos = positives&real


            precision = 0
            if len(positives)!=0:
                precision = 1.0*len(true_pos)/len(positives)

            recall = 0
            if len(real)!=0:
                recall = 1.0*len(true_pos)/len(real)

            total_docs += 1
            total_precision += precision
            total_recall += recall
            #print key, '\t', precision, '\t', recall

            total_relevant += len(real)
            total_positives += len(positives)
            total_true_pos += len(true_pos)

        precision = total_precision/total_docs
        recall = total_recall/total_docs
        fmeasure = 2.0*precision*recall/(precision+recall)

        if total_positives>0:
            mprecision = 1.0*total_true_pos/total_positives
        else:
            mprecision = 1.0
        mrecall = 1.0*total_true_pos/total_relevant
        mfmeasure = 2.0*mprecision*mrecall/(mprecision+mrecall)

        ret = {"vanila":{"precision":precision, "recall":recall, "fmeasure":fmeasure}, "micro":{"precision":mprecision, "recall":mrecall, "fmeasure":mfmeasure}}
        return ret
    
    best_macro = -1
    for theta in [0.7, 0.8, 0.9]:
        results = eval_omim(labels.keys()[:20], theta)
        #print theta
        #print print_res(results)
        if best_macro < results['vanila']['fmeasure']:
            best_macro = results['vanila']['fmeasure']
            best_theta = theta
            #test_results_for_best_theta = eval(abstracts+"labels/", output_dir, os.listdir(abstracts+"/text/")[:8], model.ont)
    results = eval_omim(labels.keys()[20:], best_theta)
    print "best theta:", best_theta
    print print_res(results)
    outfile.write(print_res(results)+"\n")
    return results

def experiment(model, exp_name):
    outfile = open("report_" + exp_name + ".txt","a")
    print "Exp:", exp_name
    outfile.write("Exp: " + exp_name +"\n")
    outfile.flush()
    num_epochs = 50
    for epoch in range(num_epochs):
        model.train_epoch(verbose=False)

    param_dir = "params_"+exp_name
    if not os.path.exists(param_dir):
        os.makedirs(param_dir)
    model.save_params(param_dir)

    samplesFile = open("data/labeled_data")
    samples = accuracy.prepare_phrase_samples(model.ont, samplesFile, True)
    hit, total = accuracy.find_phrase_accuracy(model, samples, 5, False)
    print "R@5 Accuracy on val set ::", float(hit)/total
    outfile.write("R@5 Accuracy on val set ::" + str(float(hit)/total) +"\n")

    hit, total = accuracy.find_phrase_accuracy(model, samples, 1, False)
    print "R@1 Accuracy on val set ::", float(hit)/total
    outfile.write("R@1 Accuracy on val set ::" + str(float(hit)/total) +"\n")

    abstracts = '../../datasets/abstracts/'
    udp_data = '../../datasets/udp/'
    omim_data = '../../datasets/littleomim/'

    output_dir_prefix = "outputs_" + exp_name + "_"
    abstracts_vallist_file = 'validation_abstracts'
    abstracts_testlist_file = 'test_abstracts'

    best_micro = -1
    for theta in [0.7, 0.8, 0.75, 0.85]:
        output_dir = output_dir_prefix + 'abstracts_'+ str(theta)+"/"
        create_output_dir(model, theta, abstracts+"/text/", output_dir)
        #results = eval(abstracts+"labels/", output_dir, os.listdir(abstracts+"/text/")[:8], model.ont)
        results = eval(abstracts+"labels/", output_dir, open(abstracts_vallist_file).readlines(), model.ont)
        if best_micro < results['micro']['fmeasure']:
            best_micro = results['micro']['fmeasure']
            best_theta = theta
            #test_results_for_best_theta = eval(abstracts+"labels/", output_dir, os.listdir(abstracts+"/text/")[:8], model.ont)
            test_results_for_best_theta = eval(abstracts+"labels/", output_dir, open(abstracts_testlist_file).readlines(), model.ont)

    print "Validation threshold:", best_theta
    outfile.write("Validation threshold:"+ str(best_theta) +"\n")
    print "Abstract test results:"
    outfile.write("Abstract test results:\n")
    print print_res(test_results_for_best_theta)
    outfile.write(print_res(test_results_for_best_theta)+"\n")

    udp_output_dir = output_dir_prefix+'udp_'+str(best_theta)+"/"
    create_output_dir(model, best_theta, udp_data+"/text/", udp_output_dir)
    udp_results = eval(udp_data+"labels/", udp_output_dir, os.listdir(udp_data+"/text/"), model.ont)
    #udp_results = eval(udp_data+"labels/", udp_output_dir, os.listdir(udp_data+"/text/")[:8], model.ont)
    print "UDP test results:"
    outfile.write("UDP test results:\n")
    print print_res(udp_results)
    outfile.write(print_res(udp_results)+"\n")

    omim_output_dir = output_dir_prefix+'omim_'+str(best_theta)+"/"
    create_output_dir(model, best_theta, omim_data+"/text/", omim_output_dir)
    omim_results = eval(omim_data+"labels/", omim_output_dir, os.listdir(omim_data+"/text/"), model.ont)
    print "OMIM test results:"
    outfile.write("OMIM test results:\n")
    print print_res(omim_results)
    outfile.write(print_res(omim_results)+"\n")

    outfile.flush()

def new_train(model):
    report_len = 20
    num_epochs = 50

    '''
    samplesFile = open("data/labeled_data")
    samples = accuracy.prepare_phrase_samples(model.ont, samplesFile, True)
    val_set = dict( [x for x in samples.iteritems()][:200])
    test_set = dict( [x for x in samples.iteritems()][200:])
    '''

    training_samples = {}
    for hpid in model.ont.names:
        for s in model.ont.names[hpid]:
            training_samples[s]=[hpid]

    '''
    ubs = [Ontology('data/uberon.obo', root) for root in ["UBERON:0000062", "UBERON:0000064"]]
    uberon_negs = set([name for ub in ubs for concept in ub.names for name in ub.names[concept]])

    wiki_text = open('data/wiki_text').read()
    wiki_negs = set(create_negatives(wiki_text[:10000000], 10000))
    '''

    model.init_training()
    #model.init_training(set.union(wiki_negs,uberon_negs))
    #model.init_training(wiki_negs)
    #model.init_training(uberon_negs)

    logfile = open('logfile.txt', 'w')

    for epoch in range(num_epochs):
        print "epoch ::", epoch

        loss = model.train_epoch()
        for x in model.get_hp_id(['retina cancer'], 10)[0]:
            if x[0] in model.ont.names:
                print model.ont.names[x[0]], x[1]
            else:
                print x[0], x[1]
        print "-------"
        for x in model.get_hp_id(['retinoblastoma'], 10)[0]:
            if x[0] in model.ont.names:
                print model.ont.names[x[0]], x[1]
            else:
                print x[0], x[1]
        if (epoch>0 and epoch % 5 == 0) or epoch == num_epochs-1:
            logfile.write('epoch\t'+str(epoch)+'\n')
            logfile.write('loss\t'+str(loss)+'\n')

        #    '''
        '''
            hit, total = accuracy.find_phrase_accuracy(model, samples, 5, False)
            logfile.write('r5\t'+str(float(hit)/total)+'\n')
            print "R@5 Accuracy on val set ::", float(hit)/total

            hit, total = accuracy.find_phrase_accuracy(model, samples, 1, False)
            logfile.write('r1\t'+str(float(hit)/total)+'\n')
            print "R@1 Accuracy on val set ::", float(hit)/total
        '''
        #    '''
        if False and ( ((epoch>0 and epoch % 160 == 0)) or epoch == num_epochs-1 ): 
            hit, total = accuracy.find_phrase_accuracy(model, training_samples, 1, False)
            print "Accuracy on training set ::", float(hit)/total
        sys.stdout.flush()
        logfile.flush()
    logfile.close()
    return model

def grid_search():
    config = phrase_model.Config
    rd = reader.Reader(open("data/hp.obo"), False)
    config.update_with_reader(rd)

    samplesFile = open("data/labeled_data")
    samples = accuracy.prepare_phrase_samples(rd, samplesFile, True)

    training_samples = {}
    for hpid in rd.names:
        for s in rd.names[hpid]:
            training_samples[s]=[hpid]
    
    for config.batch_size in [256, 128]:
        for config.lr in [0.002, 0.001, 0.004]:
            for config.hidden_size in [512, 1024]:
                for config.layer1_size in [1024]:
                    for config.layer2_size in [1024, 2048]:
                        config.layer3_size = config.layer2_size
                        config.layer4_size = config.layer2_size

                        model = phrase_model.NCRModel(config, rd)
                        num_epochs = 20 
                        for epoch in range(num_epochs):
                            print "epoch ::", epoch
                            model.train_epoch()
                        hit, total = accuracy.find_phrase_accuracy(model, samples, 5, False)
                        r5 = float(hit)/total
                        hit, total = accuracy.find_phrase_accuracy(model, samples, 1, False)
                        r1 = float(hit)/total
                        hit, total = accuracy.find_phrase_accuracy(model, training_samples, 1, False)
                        tr1 = float(hit)/total

                        with open("grid_results.txt","a") as testResultFile:
                            testResultFile.write('lr: ' + str(config.lr) +\
                                        '\tbatch_size ' + str(config.batch_size) +\
                                        '\thidden_size ' + str(config.hidden_size) +\
                                        '\tlayer1_size ' + str(config.layer1_size) +\
                                        '\tlayer2_size ' + str(config.layer2_size) +\
                                        '\tlayer3_size ' + str(config.layer2_size) +\
                                        '\tr5: '+ str(r5) +\
                                        '\tr1: '+ str(r1) +\
                                        '\ttr1: '+ str(tr1)+ "\n")                            

def process_text_file(model, filename, threshold=0.5):
    outfile = open("big_text_falsepos_results","w")
#   text = open('big_text_falsepos').read() ##
    text = open(filename).read() ##
    results = model.process_text(text, threshold)
    for res in results:
        outfile.write("["+str(res[0])+"::"+str(res[1])+"]\t"+str(res[2])+" | "+text[res[0]:res[1]]+"\t"+str(res[3])+"\t"+str(model.ont.names[res[2]])+"\n")
    outfile.close()
def interactive_sent(model, threshold=0.5):
    while True:
        print "Enter querry:"
        text = sys.stdin.readline()
        if text == "":
            break
        start_time = time.time()
        results = model.process_text(text, threshold)
        end_time = time.time()
        for res in results:
            print "["+str(res[0])+"::"+str(res[1])+"]\t" , res[2], "|", text[res[0]:res[1]], "\t", res[3], "\t", model.ont.names[res[2]]
        print "Time elapsed: "+ ("%.2f" % (end_time-start_time)) + "s"

def interactive(model):
    while True:
        sys.stdout.write("-----------\nEnter text:\n")
        sys.stdout.flush()
        text = sys.stdin.readline()
        sys.stdout.write("\n")
        matches = model.get_hp_id([text],15)
        for x in matches[0]:
            if x[0] == 'None':
                sys.stdout.write(x[0]+' '+str('None')+' '+str(x[1])+'\n')
            else:
                sys.stdout.write(x[0]+' '+str(model.ont.names[x[0]])+' '+str(x[1])+'\n')
        sys.stdout.write("\n")
	
def anchor_test(model):
    samples = accuracy.prepare_phrase_samples(model.rd, open("data/labeled_data"), True)
    training_samples = {}

    model.set_anchors(syns, syn_labels)
    #model.save_params(repdir)

    for x in model.get_hp_id(['retina cancer'], 10)[0]:
        print model.rd.names[x[0]], x[1]
    print "==="
    for x in model.get_hp_id(['retinal neoplasm'], 10)[0]:
        print model.rd.names[x[0]], x[1]

    hit, total = accuracy.find_phrase_accuracy(model, samples, 1, False)
    r1 = float(hit)/total
    print "R@1 Accuracy on test set ::", r1

    text_ant = sent_level.TextAnnotator(model)
    sent_window_func = lambda text: [x[2] for x in text_ant.process_text(text, 0.8, True )]
    sent_accuracy.find_sent_accuracy(sent_window_func, "labeled_sentences.p", model.rd)
#    sent_accuracy.compare_methods(sent_accuracy.biolark_wrapper.process_sent, sent_window_func, "labeled_sentences.p", model.rd)

def get_model(repdir, config):
    rd = reader.Reader("data/", True)
    #rd = reader.Reader(open("data/hp.obo"), True)
    model = phrase_model.NCRModel(config, rd)
    model.load_params(repdir)
    return model

def create_negatives(text, num):
    neg_tokens = phrase_model.tokenize(text)

    indecies = np.random.choice(len(neg_tokens), num)
    lengths = np.random.randint(1, 10, num)

    negative_phrases = [' '.join(neg_tokens[indecies[i]:indecies[i]+lengths[i]])
                                for i in range(num)]
    return negative_phrases


def sent_test(model, threshold=0.6):
  #  model.set_anchors()
    #text_ant = sent_level.TextAnnotator(model)
    #sent_window_func = lambda text: [x[2] for x in text_ant.process_text(text, 0.6, True )]
    sent_window_func = lambda text: [x[2] for x in model.process_text(text,threshold)]
    sent_accuracy.find_sent_accuracy(sent_window_func, "labeled_sentences.p", model.rd)
    #sent_accuracy.compare_methods(sent_accuracy.biolark_wrapper.process_sent, sent_window_func, "labeled_sentences.p", model.rd)

def phrase_test(model):
    samples = accuracy.prepare_phrase_samples(model.ont, open("data/labeled_data"), True)
    training_samples = {}
    for hpid in model.ont.names:
        for s in model.ont.names[hpid]:
            training_samples[s]=[hpid]

    hit, total = accuracy.find_phrase_accuracy(model, samples, 5, False)
    r5 = float(hit)/total
    print "R@5 Accuracy on test set ::", r5
    hit, total = accuracy.find_phrase_accuracy(model, samples, 1, False)
    r1 = float(hit)/total
    print "R@1 Accuracy on test set ::", r1
    #hit, total = accuracy.find_phrase_accuracy(model, training_samples, 1, False)
    #tr1 = float(hit)/total
    #print "R@1 Accuracy on training set ::", tr1

def udp_test(model, text_file, phe_file, bk_file):
    retrieved = []
    textAnt = sent_level.TextAnnotator(model)
    text = open(text_file).read()
    called = set([x[2] for x in textAnt.process_text(text, 0.6, True)])
    real_phe = set([model.rd.concepts[model.rd.name2conceptid[name.strip().lower()]] for name in open(phe_file).readlines()])

    bk_called = [model.rd.real_id[x.strip()] for x in open(bk_file).readlines()]

    print "NCR:"
    true_pos = [x for x in called if x in real_phe]
    print len(called), len(real_phe), len(true_pos)
    print "Precision:", 1.0*len(true_pos)/len(called)
    print "Recall:", 1.0*len(true_pos)/len(real_phe)

    print "Biolark:"
    bk_true_pos = [x for x in bk_called if x in real_phe]
    print len(bk_called), len(real_phe), len(bk_true_pos)
    print "Precision:", 1.0*len(bk_true_pos)/len(bk_called)
    print "Recall:", 1.0*len(bk_true_pos)/len(real_phe)

def main():
    parser = argparse.ArgumentParser(description='Hello!')
    #parser.add_argument('--repdir', help="The location where the checkpoints and the logfiles will be stored, default is \'checkpoints/\'", default="checkpoints/")
    parser.add_argument('--exp_name', help="The location where the checkpoints and the logfiles will be stored, default is \'checkpoints/\'", default="experiment")
    parser.add_argument('--no_negs', help="Would not include negative samples during training", action="store_true")
    parser.add_argument('--no_agg', action="store_true")
    parser.add_argument('--uberon', action="store_true")
    parser.add_argument('--snomed', action="store_true")
    args = parser.parse_args()

    name = args.exp_name
    if args.no_negs:
        name+='_nonegs'
    else:
        name+='_negs'

    if args.no_agg:
        name+='_noagg'
    else:
        name+='_agg'

    if args.snomed:
        name+='_snomed'
    else:
        name+='_hpo'

    if args.uberon:
        name+='_uberon'

    if args.no_negs and args.uberon:
        print "arguments are not consistent"
        exit()
    print name
    config = phrase_model.Config
#    udp_test(get_model(args.repdir, config), args.udp_prefix+".txt", args.udp_prefix+".phe", args.udp_prefix+".txt.bk")
#    interactive_sent(get_model(args.repdir, config))
#    exit()
    #sent_test(get_model(args.repdir, config))
    ###########
    '''
    model = get_model(args.repdir, config)

    ## print graph
    with  open('graph.txt','w') as graphfile:
        for hpid in model.rd.kids:
            for hpkid in model.rd.kids[hpid]:
                graphfile.write(str(model.rd.concept2id[hpid])+' '+str(model.rd.concept2id[hpkid])+'\n')
    exit()
    ## print graph
    W = model.sess.run(model.w)
    aggW = model.sess.run(model.aggregated_w)
    y = np.zeros(len(model.rd.concepts))
    y_sum = np.zeros(len(model.rd.concepts))
    top_terms = model.rd.kids["HP:0000118"]
    top_term_ids = [model.rd.concept2id[x] for x in top_terms]
    for h_id in range(len(model.rd.concepts)-1):
        for i,top_id in enumerate(top_term_ids):
            if model.rd.ancestry_mask[h_id, top_id] == 1:
                y[h_id] = i+1
        y_sum[h_id] = np.sum(model.rd.ancestry_mask[h_id,:])
 
    from tsne import bh_sne
    taggW = bh_sne(aggW.astype(np.float))
    h5f = h5py.File('embeddings.h5', 'w')
    h5f.create_dataset('W', data=W)
    h5f.create_dataset('aggW', data=aggW)
    h5f.create_dataset('taggW', data=taggW)
    h5f.create_dataset('y', data=y)
    h5f.create_dataset('y_sum', data=y_sum)
    h5f.close()
    exit()
    '''
    ###########


    #phrase_test(get_model(args.repdir, config))
    #anchor_test(get_model(args.repdir, config))

    #interactive(get_model(args.repdir, config)) 
    #exit()

    #grid_search()
    print "Loading word model" 
    word_model = fasttext.load_model('data/model_pmc.bin')
    print "Loading ontology" 
    #ont = Ontology('data/hp.obo',"HP:0000478")
    #ont = Ontology('data/small_snomed.obo',"138875005")
    if args.snomed:
        ont = Ontology('data/small_snomed.obo',"138875005")
    else:
        ont = Ontology('data/hp.obo',"HP:0000118")
    #print len(ont.concepts)

    config.agg = not args.no_agg

    print len(ont.concepts)
    model = phrase_model.NCRModel(config, ont, word_model)
#    model.init_training()
#    new_train(model)

    #wiki_text = open('data/wiki_text').read()
    #wiki_negs = set(create_negatives(wiki_text[:10000000], 10000))
    #model.init_training(wiki_negs)
    if args.no_negs:
        model.init_training()
    else:
        wiki_text = open('data/wiki_text').read()
        wiki_negs = set(create_negatives(wiki_text[:10000000], 10000))
        if args.uberon:
            ubs = [Ontology('data/uberon.obo', root) for root in ["UBERON:0000062", "UBERON:0000064"]]
            uberon_negs = set([ubname for ub in ubs for concept in ub.names for ubname in ub.names[concept]])
            model.init_training(wiki_negs.union(uberon_negs))
        else:
            model.init_training(wiki_negs)

    #new_train(model)
#    model.load_params('mimic_params/')
    #model.save_params('mimic_params_agg/')
#    print mimic_experiment(model)
    #model.save_params(args.repdir)


    if args.snomed:
        mimic_experiment(model, name)
    else:
        experiment(model, name)
    exit()
    '''
    model.load_params('params_wiki_aggregate_aug24/')
    filename = 'big_text_falsepos'
    process_text_file(model, filename, 0.7) 
    #interactive_sent(model, 0.7)
    exit()
    '''
    

#    model = phrase_model.NCRModel(config, ont, word_model)
    '''
    model.load_params('params_wiki_aggregate_noclassw/')
    best_theta = 0.6
    exp_name = 'wiki_aggregate_noclassw_foromim'
    output_dir_prefix = "outputs_" + exp_name + "_"
    omim_output_dir = output_dir_prefix+'omim_'+str(best_theta)+"/"
    omim_data = '../../datasets/littleomim/'
    create_output_dir(model, best_theta, omim_data+"/text/", omim_output_dir)
    omim_results = eval(omim_data+"labels/", omim_output_dir, os.listdir(omim_data+"/text/"), model.ont)
    print "omim test results:"
    print print_res(omim_results)
    '''


##    interactive_sent(model, 0.6)
#    phrase_test(model)
    #interactive(model)
    #model = new_train(phrase_model.NCRModel(config, ont, word_model))
    #model.save_params(args.repdir)

    '''
    models = [new_train(phrase_model.NCRModel(config, ont, word_model)) for i in range(5)]
    ens = Ensemle(models, ont)
    for i,m in enumerate(models):
        print "model",i
        phrase_test(m)
    print "Ensemle model"
    phrase_test(ens)
    '''

    '''
    model = phrase_model.NCRModel(config, ont, word_model)
    model.load_params(args.repdir)
    interactive(model)
    return 
    phrase_test(model)
    '''

if __name__ == "__main__":
	main()

